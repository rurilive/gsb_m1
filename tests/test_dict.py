"""预共享字典的验收：训练、版本管理、带字典编解码。"""

import time
import tempfile
import unittest

from demo import make_corpus
from msglz import (
    DictStore,
    DictVersionError,
    FormatError,
    MessageCodec,
    frame,
    lz,
    train_dictionary,
)


class TrainTest(unittest.TestCase):
    def test_size_limit_and_nonempty(self):
        dictionary = train_dictionary(make_corpus(500, seed=3), 1024)
        self.assertTrue(0 < len(dictionary) <= 1024)

    def test_empty_inputs(self):
        self.assertEqual(train_dictionary([], 512), b"")
        self.assertEqual(train_dictionary(make_corpus(10, seed=1), 0), b"")


class DictStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.corpus = make_corpus(300, seed=11)

    def make_store(self, **kw):
        return DictStore(self.tmp.name, **kw)

    def test_roundtrip_byte_identical_and_matches_plain_codec(self):
        store = self.make_store(min_gain=0.0)
        self.assertTrue(store.rollout(self.corpus)["deployed"])
        plain = MessageCodec()
        for message in self.corpus:
            via_dict = store.decode(store.encode(message))
            via_plain = plain.decode(plain.encode(message))
            self.assertEqual(via_dict, message)
            self.assertEqual(via_plain, message)
            self.assertEqual(via_dict, via_plain)

    def test_saves_quarter_on_short_messages(self):
        store = self.make_store(min_gain=0.0)
        store.rollout(self.corpus)
        plain = MessageCodec()
        plain_total = sum(len(plain.encode(m)) for m in self.corpus)
        dict_total = sum(len(store.encode(m)) for m in self.corpus)
        self.assertLessEqual(dict_total, plain_total * 0.75)

    def test_train_10k_under_20_seconds(self):
        corpus = make_corpus(10000, seed=5)
        store = self.make_store(min_gain=0.0)
        started = time.perf_counter()
        store.rollout(corpus)
        self.assertLess(time.perf_counter() - started, 20.0)

    def test_encode_before_any_rollout(self):
        store = self.make_store()
        for message in self.corpus[:10]:
            self.assertEqual(store.decode(store.encode(message)), message)

    def test_mz1_frames_still_decode(self):
        store = self.make_store(min_gain=0.0)
        store.rollout(self.corpus)
        codec = MessageCodec()
        for message in self.corpus[:20]:
            self.assertEqual(store.decode(codec.encode(message)), message)

    def test_versions_coexist_and_oldest_evicted(self):
        store = self.make_store(max_versions=2, min_gain=0.0)
        frames = {}
        for _ in range(3):
            report = store.rollout(self.corpus)
            self.assertTrue(report["deployed"])
            frames[report["version"]] = store.encode(self.corpus[0])
        self.assertEqual(store.versions(), (2, 3))
        # 现役与上一版共存，都能解
        self.assertEqual(store.decode(frames[3]), self.corpus[0])
        self.assertEqual(store.decode(frames[2]), self.corpus[0])
        # v1 已淘汰：当场报错，异常带版本号
        with self.assertRaises(DictVersionError) as ctx:
            store.decode(frames[1])
        self.assertEqual(ctx.exception.version, 1)

    def test_unknown_version_rejected(self):
        store = self.make_store()
        data = b"hello hello hello hello"
        blob = lz.compress(data)
        bad = (
            b"MZ2"
            + bytes([frame.KIND_LZ])
            + lz.encode_varint(99)
            + lz.encode_varint(len(data))
            + blob
            + frame.fnv32(data).to_bytes(4, "big")
        )
        with self.assertRaises(DictVersionError) as ctx:
            store.decode(bad)
        self.assertEqual(ctx.exception.version, 99)

    def test_rollout_rolls_back_when_gain_too_small(self):
        store = self.make_store(min_gain=0.99)
        report = store.rollout(self.corpus)
        self.assertFalse(report["deployed"])
        self.assertIsNone(report["version"])
        self.assertEqual(store.active_version, 0)
        self.assertEqual(store.versions(), ())
        self.assertIn("candidate_ratio", report)
        self.assertIn("baseline_ratio", report)

    def test_versions_survive_reload(self):
        store = self.make_store(min_gain=0.0)
        store.rollout(self.corpus)
        packed = store.encode(self.corpus[0])
        again = self.make_store(min_gain=0.0)
        self.assertEqual(again.active_version, store.active_version)
        self.assertEqual(again.decode(packed), self.corpus[0])

    def test_garbage_frames_raise_format_error(self):
        store = self.make_store(min_gain=0.0)
        store.rollout(self.corpus)
        packed = bytearray(store.encode(self.corpus[0]))
        with self.assertRaises(FormatError):
            store.decode(bytes(packed[:-2]))
        packed[-1] ^= 0xFF
        with self.assertRaises(FormatError):
            store.decode(bytes(packed))
        with self.assertRaises(FormatError):
            store.decode(b"NOPE not a frame")


if __name__ == "__main__":
    unittest.main()
