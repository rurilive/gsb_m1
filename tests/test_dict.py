"""预共享字典的验收测试：训练、版本管理、帧兼容与性能。"""

import os
import random
import tempfile
import time
import unittest

from msglz import (
    DictStore,
    DictVersionError,
    FormatError,
    MessageCodec,
    frame,
    lz,
    train_dictionary,
)
from demo import make_corpus


def _payment_corpus(count, seed=1):
    """支付域短消息，结构跟 demo 的总线语料完全不同。"""
    rnd = random.Random(seed)
    out = []
    for i in range(count):
        stamp = 1758300000 + i * rnd.randint(1, 9)
        out.append((
            "2026-09-21T%02d:%02d:%02dZ PAY order=%d amount=%.2f "
            "currency=USD card=****%d merchant=m%d status=%s" % (
                (stamp // 3600) % 24, (stamp // 60) % 60, stamp % 60,
                rnd.randrange(10 ** 6), rnd.randrange(100, 9900) / 100,
                rnd.randrange(1000, 9999), rnd.randrange(50),
                rnd.choice(["OK", "FAIL"]))).encode())
    return out


def _http_corpus(count, seed=1):
    """HTTP 访问日志型短消息。"""
    rnd = random.Random(seed)
    paths = ["/api/v1/orders", "/api/v1/users", "/healthz",
             "/api/v2/cart/items"]
    out = []
    for i in range(count):
        stamp = 1758300000 + i
        out.append((
            '10.%d.0.%d - - [21/Sep/2026:%02d:%02d:%02d +0800] '
            '"%s %s HTTP/1.1" %d %d rt=%dms req-id=%08x' % (
                rnd.randrange(256), rnd.randrange(256),
                (stamp // 3600) % 24, (stamp // 60) % 60, stamp % 60,
                rnd.choice(["GET", "POST", "PUT"]), rnd.choice(paths),
                rnd.choice([200, 200, 404, 500]), rnd.randrange(5000),
                rnd.randrange(300), rnd.getrandbits(32))).encode())
    return out


def _inventory_corpus(count, seed=1):
    """库存事件型短消息。"""
    rnd = random.Random(seed)
    zones = ["cn-hz-a", "cn-sh-b", "ap-sg-c"]
    out = []
    for i in range(count):
        stamp = 1758300000 + i * 3
        out.append((
            "INV|ts=%d|sku=SKU-%06d|wh=%s|qty=%d|batch=B%04d|"
            "event=stock.%s|pos=P%d" % (
                stamp, rnd.randrange(10 ** 6), rnd.choice(zones),
                rnd.randrange(10000), rnd.randrange(10000),
                rnd.choice(["in", "out", "hold", "release"]),
                rnd.randrange(20))).encode())
    return out


class TrainDictionaryTest(unittest.TestCase):
    def test_empty_and_tiny_budget(self):
        self.assertEqual(train_dictionary([], 100), b"")
        self.assertEqual(train_dictionary([b"short"], 100), b"")
        self.assertEqual(train_dictionary([b"repeated phrase"] * 4, 5), b"")

    def test_negative_budget(self):
        with self.assertRaises(ValueError):
            train_dictionary([b"whatever"], -1)

    def test_finds_repeated_fragments_within_budget(self):
        samples = [
            b"prefix order.created id=%d node=cn-a" % i for i in range(20)
        ]
        dictionary = train_dictionary(samples, 128)
        self.assertIn(b"order.created", dictionary)
        self.assertLessEqual(len(dictionary), 128)

    def test_accepts_iterable_and_bytearray(self):
        samples = (bytearray(b"shared-keyword-%d" % i) for i in range(10))
        dictionary = train_dictionary(samples, 128)
        self.assertIn(b"shared-keyword", dictionary)

    def test_random_corpus_trains_nothing_useful(self):
        rnd = random.Random(1)
        samples = [rnd.randbytes(120) for _ in range(40)]
        self.assertEqual(train_dictionary(samples, 4096), b"")


class DictRoundTripTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.corpus = make_corpus(200, seed=7)
        self.store = DictStore(self.tmp.name)

    def test_rollout_promotes_and_roundtrips(self):
        report = self.store.rollout(self.corpus)
        self.assertTrue(report["promoted"])
        self.assertGreater(self.store.active_version, 0)
        for message in self.corpus:
            packed = self.store.encode(message)
            self.assertEqual(self.store.decode(packed), message)

    def test_byte_for_byte_against_no_dict_path(self):
        codec = MessageCodec()
        self.store.rollout(self.corpus)
        for message in self.corpus:
            plain_frame = codec.encode(message)
            self.assertEqual(self.store.decode(plain_frame), message)
            self.assertEqual(codec.decode(plain_frame), message)

    def test_old_lz_and_raw_frames_decode(self):
        codec = MessageCodec()
        for message in (b"order.created " * 6, os.urandom(24)):
            old_frame = codec.encode(message)
            self.assertEqual(self.store.decode(old_frame), message)

    def test_encode_without_active_matches_codec_bytes(self):
        codec = MessageCodec()
        message = self.corpus[0]
        self.assertIsNone(self.store.active_version)
        self.assertEqual(self.store.encode(message), codec.encode(message))

    def test_checksum_still_rejects_corruption(self):
        self.store.rollout(self.corpus)
        packed = bytearray(self.store.encode(self.corpus[3]))
        packed[-1] ^= 0x01
        with self.assertRaises(FormatError):
            self.store.decode(bytes(packed))

    def test_truncated_dict_frame(self):
        self.store.rollout(self.corpus)
        packed = self.store.encode(self.corpus[3])
        with self.assertRaises(FormatError):
            self.store.decode(packed[:-2])


class CompressionGainTest(unittest.TestCase):
    def test_dict_cuts_total_size_by_a_quarter(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        corpus = make_corpus(200, seed=7)
        store = DictStore(tmp.name)
        report = store.rollout(corpus)
        self.assertTrue(report["promoted"])
        raw_total = sum(len(message) for message in corpus)
        plain_total = sum(len(MessageCodec().encode(message))
                          for message in corpus)
        dict_total = sum(len(store.encode(message)) for message in corpus)
        # 真算带字典编码总量（含帧头与版本号），不是只看压缩体。
        self.assertLessEqual(dict_total, plain_total * 3 // 4)
        self.assertLess(dict_total, raw_total)
        # 帧头确确实实带了字典版本号。
        kind, _raw_len, payload, _checksum = frame.unpack_frame(
            store.encode(corpus[0]))
        self.assertEqual(kind, frame.KIND_LZ_DICT)
        version, pos = lz.decode_varint(payload, 0)
        self.assertEqual(version, store.active_version)
        self.assertLess(pos, len(payload))


class RolloutPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = DictStore(self.tmp.name, min_gain=0.05)

    def test_first_rollout_is_measured_against_no_dict(self):
        report = self.store.rollout(make_corpus(200, seed=7))
        self.assertTrue(report["promoted"])
        self.assertIsNone(report["baseline_version"])
        self.assertGreater(report["gain"], report["min_gain"])
        self.assertEqual(report["baseline_ratio"], report["baseline_bytes"]
                         / report["raw_bytes"])

    def test_weak_rollout_is_rejected_and_everything_stays(self):
        good = make_corpus(200, seed=7)
        first = self.store.rollout(good)
        self.assertTrue(first["promoted"])
        active = self.store.active_version

        rnd = random.Random(99)
        junk = [rnd.randbytes(110) for _ in range(200)]
        second = self.store.rollout(junk)
        self.assertFalse(second["promoted"])
        self.assertEqual(second["dict_size"], 0)
        self.assertGreater(second["version"], active)
        self.assertLess(second["gain"], second["min_gain"])
        self.assertTrue(second["reason"])
        # 现役与字典内容原样退回。
        self.assertEqual(self.store.active_version, active)
        self.assertEqual(self.store.versions(), [active])
        before = self.store.dictionary(active)
        for message in good[:10]:
            packed = self.store.encode(message)
            kind, _l, payload, _c = frame.unpack_frame(packed)
            if kind == frame.KIND_LZ_DICT:
                version, _pos = lz.decode_varint(payload, 0)
                self.assertEqual(version, active)
            self.assertEqual(self.store.decode(packed), message)
        self.assertEqual(self.store.dictionary(active), before)

    def test_marginal_gain_below_threshold_keeps_active(self):
        good = make_corpus(300, seed=7)
        self.assertTrue(self.store.rollout(good)["promoted"])
        active = self.store.active_version
        sameish = make_corpus(300, seed=8)
        report = self.store.rollout(sameish)
        self.assertFalse(report["promoted"])
        self.assertEqual(self.store.active_version, active)
        self.assertIn(str(active), report["reason"])


class VersioningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_versions_coexist_and_old_frames_still_decode(self):
        store = DictStore(self.tmp.name, max_versions=3, min_gain=0.0)
        domains = (_payment_corpus, _http_corpus, _inventory_corpus)
        probes = [domain(1)[0] for domain in domains]
        frames_by_version = {}
        for domain in domains:
            report = store.rollout(domain(300))
            self.assertTrue(report["promoted"])
            version = report["version"]
            frames_by_version[version] = store.encode(probes[version - 1])
        self.assertEqual(len(store.versions()), 3)
        self.assertEqual(len(set(frames_by_version)), 3)
        reopened = DictStore(self.tmp.name, max_versions=3, min_gain=0.0)
        self.assertEqual(reopened.versions(), list(frames_by_version))
        for version, packed in frames_by_version.items():
            self.assertIn(version, reopened.versions())
            kind, _raw_len, payload, _checksum = frame.unpack_frame(packed)
            self.assertEqual(kind, frame.KIND_LZ_DICT)
            packed_version, _pos = lz.decode_varint(payload, 0)
            self.assertEqual(packed_version, version)
            self.assertEqual(reopened.decode(packed), probes[version - 1])

    def test_eviction_drops_oldest_and_its_frames_fail_loudly(self):
        store = DictStore(self.tmp.name, max_versions=2, min_gain=0.0)
        domains = (_payment_corpus, _http_corpus, _inventory_corpus)
        reports = [store.rollout(domain(300)) for domain in domains]
        versions = [report["version"] for report in reports]
        self.assertTrue(all(report["promoted"] for report in reports))
        oldest, middle, newest = versions
        self.assertEqual(store.versions(), [middle, newest])
        self.assertEqual(store.active_version, newest)
        old_dict = train_dictionary(_payment_corpus(300), 4096)
        message = b"2026-09-21T00:00:00Z INFO order.created id=1 old payload"
        body = (lz.encode_varint(oldest)
                + lz.compress(message, preset=old_dict))
        old_frame = frame.pack_frame(
            frame.KIND_LZ_DICT, len(message), body, frame.fnv32(message))
        with self.assertRaises(DictVersionError) as caught:
            store.decode(old_frame)
        self.assertEqual(caught.exception.version, oldest)
        with self.assertRaises(DictVersionError) as caught:
            store.dictionary(oldest)
        self.assertEqual(caught.exception.version, oldest)

    def test_never_seen_version_fails_with_version_in_error(self):
        store = DictStore(self.tmp.name)
        store.rollout(make_corpus(120, seed=1))
        fake = frame.pack_frame(
            frame.KIND_LZ_DICT, 4, b"\x7f\x00\x00\x00\x00",
            frame.fnv32(b"what"))
        with self.assertRaises(DictVersionError) as caught:
            store.decode(fake)
        self.assertEqual(caught.exception.version, 127)

    def test_persistence_round_trip(self):
        store = DictStore(self.tmp.name, max_versions=2, min_gain=0.0)
        store.rollout(make_corpus(120, seed=1))
        message = make_corpus(1, seed=55)[0]
        packed = store.encode(message)
        reopened = DictStore(self.tmp.name, max_versions=2, min_gain=0.0)
        self.assertEqual(reopened.active_version, store.active_version)
        self.assertEqual(reopened.decode(packed), message)


class PerformanceTest(unittest.TestCase):
    def test_ten_thousand_samples_train_within_twenty_seconds(self):
        corpus = make_corpus(10000, seed=13)
        started = time.perf_counter()
        dictionary = train_dictionary(corpus, 4096)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 20.0)
        self.assertLessEqual(len(dictionary), 4096)


if __name__ == "__main__":
    unittest.main()
