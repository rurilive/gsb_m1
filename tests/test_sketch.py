"""BucketSketch 的行为测试。

覆盖：空与小基数不起飞、多档基数误差、定容内存、merge 代数性质、
fmt 2 落盘往返、老 fmt 1 迁移与前向加字段兼容。
"""

import json
import os
import tempfile
import unittest

from dedupkit import BucketSketch, codec
from dedupkit.ledger import Ledger


def feed(sketch, count, prefix="u"):
    for i in range(count):
        sketch.add(f"{prefix}-{i}")


def relative_error(estimate, exact):
    return abs(estimate - exact) / exact


class TestEstimation(unittest.TestCase):
    def test_empty_sketch_counts_zero(self):
        self.assertEqual(BucketSketch().count(), 0.0)

    def test_small_cardinality_stays_sane(self):
        # 数据比桶还少时不许出离奇的数
        for exact in range(1, 40):
            sketch = BucketSketch(bits=10, seed=3)
            feed(sketch, exact)
            self.assertLess(
                relative_error(sketch.count(), exact),
                0.15,
                msg=f"n={exact}, est={sketch.count()}",
            )

    def test_small_cardinality_with_collisions_present(self):
        sketch = BucketSketch(bits=8)
        feed(sketch, 50)
        self.assertLess(relative_error(sketch.count(), 50), 0.15)

    def test_multiple_cardinalities_within_a_few_percent(self):
        cases = [
            (1000, 0.05),
            (4096, 0.05),
            (10000, 0.08),
            (50000, 0.06),
            (200000, 0.05),
        ]
        for exact, tolerance in cases:
            with self.subTest(exact=exact):
                sketch = BucketSketch(bits=12, seed=11)
                feed(sketch, exact)
                self.assertLess(
                    relative_error(sketch.count(), exact), tolerance
                )

    def test_error_is_not_systematically_biased(self):
        errors = []
        for seed in range(8):
            sketch = BucketSketch(bits=12, seed=seed)
            feed(sketch, 50000)
            errors.append((sketch.count() - 50000) / 50000)
        self.assertLess(abs(sum(errors) / len(errors)), 0.02)

    def test_duplicate_adds_do_not_change_estimate(self):
        sketch = BucketSketch()
        feed(sketch, 5000)
        before = sketch.count()
        before_registers = sketch.registers()
        for i in range(5000):
            sketch.add(f"u-{i}")
        self.assertEqual(sketch.count(), before)
        self.assertEqual(sketch.registers(), before_registers)

    def test_supported_key_types_all_hash(self):
        sketch = BucketSketch()
        for key in ["s", 42, True, b"raw", (1, "x"), None]:
            sketch.add(key)
        self.assertGreater(sketch.count(), 4.0)

    def test_unsupported_key_type_raises(self):
        sketch = BucketSketch()
        with self.assertRaises(ValueError):
            sketch.add(["not", "encodable"])

    def test_other_seed_gives_different_registers(self):
        first = BucketSketch(12, seed=0)
        second = BucketSketch(12, seed=999)
        feed(first, 5000)
        feed(second, 5000)
        self.assertNotEqual(first.registers(), second.registers())

    def test_invalid_bits_rejected(self):
        with self.assertRaises(ValueError):
            BucketSketch(bits=3)
        with self.assertRaises(ValueError):
            BucketSketch(bits=19)
        with self.assertRaises(TypeError):
            BucketSketch(bits=12.0)


class TestMemoryFootprint(unittest.TestCase):
    def test_registers_are_fixed_size_bytes(self):
        sketch = BucketSketch(bits=12)
        empty_size = len(sketch.registers())
        feed(sketch, 300000)
        self.assertEqual(len(sketch.registers()), empty_size)
        self.assertEqual(empty_size, 4096)

    def test_estimate_stays_usable_after_hundreds_of_thousands(self):
        sketch = BucketSketch(bits=12, seed=5)
        feed(sketch, 300000)
        self.assertLess(relative_error(sketch.count(), 300000), 0.05)


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.left_keys = [f"L-{i}" for i in range(20000)]
        overlap = [f"L-{i}" for i in range(0, 5000, 2)]
        self.right_keys = [f"R-{i}" for i in range(15000)] + overlap

    def build(self):
        left = BucketSketch(12, seed=42)
        right = BucketSketch(12, seed=42)
        union = BucketSketch(12, seed=42)
        for key in self.left_keys:
            left.add(key)
        for key in self.right_keys:
            right.add(key)
        for key in self.left_keys + self.right_keys:
            union.add(key)
        return left, right, union

    def test_merge_matches_building_union_from_scratch(self):
        left, right, union = self.build()
        merged = left.merge(right)
        self.assertEqual(merged.registers(), union.registers())
        self.assertEqual(merged.count(), union.count())

    def test_merge_leaves_inputs_untouched(self):
        left, right, _ = self.build()
        left_before = left.registers()
        right_before = right.registers()
        left.merge(right)
        self.assertEqual(left.registers(), left_before)
        self.assertEqual(right.registers(), right_before)

    def test_merge_is_order_and_repeat_independent(self):
        left, right, union = self.build()
        one = left.merge(right)
        two = right.merge(left)
        three = one.merge(one).merge(two)
        self.assertEqual(one.registers(), two.registers())
        self.assertEqual(three.registers(), union.registers())

    def test_merge_with_empty_is_identity(self):
        left, _, _ = self.build()
        merged = BucketSketch(12, seed=42).merge(left)
        self.assertEqual(merged.registers(), left.registers())

    def test_merge_rejects_mismatched_parameters(self):
        left = BucketSketch(12, seed=1)
        right = BucketSketch(11, seed=1)
        with self.assertRaises(ValueError):
            left.merge(right)
        other_seed = BucketSketch(12, seed=2)
        with self.assertRaises(ValueError):
            left.merge(other_seed)

    def test_merge_rejects_non_sketch(self):
        with self.assertRaises(TypeError):
            BucketSketch().merge("nope")


class TestSketchCodec(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "sketch.json")

    def read_raw(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_roundtrip_restores_registers_exactly(self):
        sketch = BucketSketch(12, seed=77)
        feed(sketch, 12345)
        codec.save_sketch(sketch, self.path)
        back = codec.load(self.path)
        self.assertIsInstance(back, BucketSketch)
        self.assertEqual(back.bits, 12)
        self.assertEqual(back.seed, 77)
        self.assertEqual(back.registers(), sketch.registers())
        self.assertEqual(back.count(), sketch.count())

    def test_roundtrip_sketch_can_keep_merging(self):
        left = BucketSketch(12, seed=9)
        right = BucketSketch(12, seed=9)
        feed(left, 4000, prefix="a")
        feed(right, 4000, prefix="b")
        codec.save_sketch(left, self.path)
        restored = codec.load(self.path)
        self.assertEqual(
            restored.merge(right).registers(), left.merge(right).registers()
        )

    def test_saving_twice_produces_identical_bytes(self):
        sketch = BucketSketch(12, seed=1)
        feed(sketch, 1000)
        codec.save_sketch(sketch, self.path)
        first = self.read_raw()
        codec.save_sketch(sketch, self.path)
        self.assertEqual(first, self.read_raw())

    def test_format_marker_is_two(self):
        codec.save_sketch(BucketSketch(), self.path)
        document = json.loads(self.read_raw())
        self.assertEqual(document["fmt"], 2)
        self.assertEqual(document["kind"], "sketch")
        self.assertEqual(document["sketch"]["bits"], 12)

    def test_extra_fields_do_not_break_load(self):
        codec.save_sketch(BucketSketch(11, seed=3), self.path)
        document = json.loads(self.read_raw())
        document["future"] = {"nested": "ok"}
        document["sketch"]["extra"] = [1, 2, 3]
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        back = codec.load(self.path)
        self.assertEqual(back.bits, 11)
        self.assertEqual(back.seed, 3)

    def test_corrupt_registers_length_raises(self):
        codec.save_sketch(BucketSketch(10), self.path)
        document = json.loads(self.read_raw())
        document["sketch"]["registers"] = "AA"  # 长度对不上 1024
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_corrupt_base64_raises(self):
        codec.save_sketch(BucketSketch(), self.path)
        document = json.loads(self.read_raw())
        document["sketch"]["registers"] = "@@@not-base64"
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_missing_sketch_body_raises(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"fmt": 2, "kind": "sketch"}, handle)
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_save_sketch_rejects_ledger(self):
        with self.assertRaises(TypeError):
            codec.save_sketch(Ledger(), self.path)


class TestLegacyMigration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "ledger.json")

    def test_fmt_one_file_still_loads_as_ledger(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        ledger.add("b", "u1")
        codec.save(ledger, self.path)
        back = codec.load(self.path)
        self.assertIsInstance(back, Ledger)
        self.assertEqual(back.total(), 2)

    def test_legacy_data_can_feed_sketch_and_merge_on(self):
        ledger = Ledger()
        for name in ("a", "b"):
            for i in range(2000):
                ledger.add(name, f"{name}-{i}")
            for i in range(500):
                ledger.add(name, f"shared-{i}")
        codec.save(ledger, self.path)
        restored = codec.load(self.path)

        migrated = BucketSketch(12, seed=0)
        for name in restored.names():
            for key in restored.keys(name):
                migrated.add(key)

        expected = BucketSketch(12, seed=0)
        for name in ledger.names():
            for key in ledger.keys(name):
                expected.add(key)
        self.assertEqual(migrated.registers(), expected.registers())

        recent = BucketSketch(12, seed=0)
        feed(recent, 3000, prefix="fresh")
        merged = migrated.merge(recent)
        fresh_union = BucketSketch(12, seed=0)
        for name in ledger.names():
            for key in ledger.keys(name):
                fresh_union.add(key)
        feed(fresh_union, 3000, prefix="fresh")
        self.assertEqual(merged.registers(), fresh_union.registers())


if __name__ == "__main__":
    unittest.main()
