"""BucketSketch 与估算器落盘的行为测试。"""

import json
import os
import tempfile
import unittest

from dedupkit import BucketSketch, Ledger, codec


def feed(sketch, keys):
    for key in keys:
        sketch.add(key)
    return sketch


class TestEstimate(unittest.TestCase):
    def test_empty_sketch_counts_zero(self):
        self.assertEqual(BucketSketch().count(), 0)

    def test_tiny_data_stays_sane(self):
        sketch = BucketSketch()
        for key in ["a", "b", "c"]:
            sketch.add(key)
        self.assertLessEqual(abs(sketch.count() - 3), 1)

    def test_duplicate_adds_do_not_inflate(self):
        sketch = BucketSketch()
        for _ in range(1000):
            sketch.add("same-key")
        self.assertLessEqual(abs(sketch.count() - 1), 1)

    def test_accuracy_across_scales(self):
        for size in (50, 500, 5000, 50000, 200000):
            keys = [f"user-{i}" for i in range(size)]
            sketch = feed(BucketSketch(), keys)
            estimate = sketch.count()
            error = abs(estimate - size) / size
            self.assertLess(
                error, 0.05, f"n={size}: 估算 {estimate}，相对误差 {error:.2%}"
            )

    def test_no_systematic_bias_across_seeds(self):
        size = 20000
        keys = [f"user-{i}" for i in range(size)]
        estimates = [feed(BucketSketch(seed=seed), keys).count() for seed in range(8)]
        mean = sum(estimates) / len(estimates)
        self.assertLess(abs(mean - size) / size, 0.02)

    def test_memory_footprint_is_fixed(self):
        sketch = BucketSketch()
        self.assertTrue(1024 <= len(sketch.registers()) <= 8192)
        before = len(sketch.registers())
        feed(sketch, (f"user-{i}" for i in range(300000)))
        self.assertEqual(len(sketch.registers()), before)

    def test_add_reports_register_bump(self):
        sketch = BucketSketch()
        self.assertTrue(sketch.add("u1"))
        self.assertFalse(sketch.add("u1"))

    def test_constructor_validation(self):
        with self.assertRaises(ValueError):
            BucketSketch(bits=3)
        with self.assertRaises(ValueError):
            BucketSketch(bits=17)
        with self.assertRaises(TypeError):
            BucketSketch(bits="12")
        with self.assertRaises(ValueError):
            BucketSketch(seed=-1)
        with self.assertRaises(TypeError):
            BucketSketch(seed=1.5)


class TestMerge(unittest.TestCase):
    def test_merge_matches_fresh_build(self):
        left_keys = [f"a-{i}" for i in range(3000)]
        right_keys = [f"b-{i}" for i in range(2000)] + left_keys[:500]
        left = feed(BucketSketch(), left_keys)
        right = feed(BucketSketch(), right_keys)
        merged = left.merge(right)
        fresh = feed(BucketSketch(), left_keys + right_keys)
        self.assertEqual(merged.registers(), fresh.registers())
        self.assertEqual(merged.count(), fresh.count())

    def test_merge_leaves_inputs_untouched(self):
        left = feed(BucketSketch(), [f"a-{i}" for i in range(100)])
        right = feed(BucketSketch(), [f"b-{i}" for i in range(100)])
        left_before, right_before = left.registers(), right.registers()
        left.merge(right)
        self.assertEqual(left.registers(), left_before)
        self.assertEqual(right.registers(), right_before)

    def test_merge_is_order_independent_and_idempotent(self):
        parts = []
        for shard in range(4):
            parts.append(feed(BucketSketch(), [f"s{shard}-{i}" for i in range(500)]))
        forward = parts[0].merge(parts[1]).merge(parts[2]).merge(parts[3])
        backward = parts[3].merge(parts[2]).merge(parts[1]).merge(parts[0])
        self.assertEqual(forward.registers(), backward.registers())
        self.assertEqual(forward.merge(forward).registers(), forward.registers())
        self.assertEqual(parts[0].merge(parts[0]).registers(), parts[0].registers())

    def test_merge_rejects_mismatched_params(self):
        with self.assertRaises(ValueError):
            BucketSketch(bits=10).merge(BucketSketch(bits=12))
        with self.assertRaises(ValueError):
            BucketSketch(seed=1).merge(BucketSketch(seed=2))
        with self.assertRaises(TypeError):
            BucketSketch().merge(Ledger())


class TestSketchCodec(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "sketch.json")

    def read_document(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_roundtrip_keeps_registers_exact(self):
        sketch = feed(BucketSketch(bits=11, seed=7), [f"u{i}" for i in range(5000)])
        codec.save(sketch, self.path)
        back = codec.load(self.path)
        self.assertIsInstance(back, BucketSketch)
        self.assertEqual(back.bits, 11)
        self.assertEqual(back.seed, 7)
        self.assertEqual(back.registers(), sketch.registers())
        self.assertEqual(back.count(), sketch.count())

    def test_loaded_sketch_still_merges(self):
        left = feed(BucketSketch(), [f"a-{i}" for i in range(800)])
        right = feed(BucketSketch(), [f"b-{i}" for i in range(800)])
        codec.save(left, self.path)
        back = codec.load(self.path)
        merged = back.merge(right)
        fresh = feed(BucketSketch(), [f"a-{i}" for i in range(800)])
        self.assertEqual(merged.registers(), fresh.merge(right).registers())

    def test_sketch_save_is_deterministic(self):
        sketch = feed(BucketSketch(), [f"u{i}" for i in range(1000)])
        codec.save(sketch, self.path)
        with open(self.path, "rb") as handle:
            first = handle.read()
        codec.save(sketch, self.path)
        with open(self.path, "rb") as handle:
            self.assertEqual(first, handle.read())

    def test_extra_fields_in_sketch_file_are_ignored(self):
        sketch = feed(BucketSketch(), [f"u{i}" for i in range(100)])
        codec.save(sketch, self.path)
        document = self.read_document()
        document["note"] = "后来加的字段"
        document["future"] = {"nested": [1, 2, 3]}
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        back = codec.load(self.path)
        self.assertEqual(back.registers(), sketch.registers())

    def test_old_ledger_file_still_loads_and_feeds_sketch(self):
        ledger = Ledger()
        for i in range(200):
            ledger.add("old", f"u{i}")
        codec.save(ledger, self.path)
        self.assertEqual(self.read_document()["fmt"], 1)
        back = codec.load(self.path)
        self.assertIsInstance(back, Ledger)
        sketch = BucketSketch()
        for name in back.names():
            for key in back.keys(name):
                sketch.add(key)
        fresh = feed(BucketSketch(), [f"u{i}" for i in range(200)])
        self.assertEqual(sketch.registers(), fresh.registers())

    def test_bad_sketch_files_raise_valueerror(self):
        sketch = feed(BucketSketch(), ["u1"])
        codec.save(sketch, self.path)
        base = self.read_document()
        for mutate in (
            lambda doc: doc.update(kind="ledger"),
            lambda doc: doc.update(registers="!!!not-base64!!!"),
            lambda doc: doc.update(registers="AQID"),  # 长度对不上
            lambda doc: doc.update(bits="12"),
            lambda doc: doc.pop("seed"),
        ):
            document = dict(base)
            mutate(document)
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            with self.assertRaises(ValueError):
                codec.load(self.path)

    def test_from_registers_validation(self):
        with self.assertRaises(ValueError):
            BucketSketch.from_registers(12, 0, b"\x00" * 10)
        with self.assertRaises(ValueError):
            BucketSketch.from_registers(4, 0, bytes([200] * 16))


if __name__ == "__main__":
    unittest.main()
