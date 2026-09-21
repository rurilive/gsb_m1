"""压缩块后端的行为测试。

覆盖：与裸存 RawStore 的随机对拍、压缩率真算、块头二分与单块解码
计数、坏块（校验不过/截断）跳过、老裸存文件兼容不迁移、百万级写入
与随机访问的性能红线。
"""

import os
import random
import struct
import tempfile
import time
import unittest

from tstore import TsStore
from tstore.blocks import BLOCK_HEADER, FILE_HEADER
from tstore.errors import TsFormatError
from tstore.layout import HEADER as RAW_MAGIC
from tstore.raw import RawStore


class BlockCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "points.blk")

    def open(self, path=None, **kwargs):
        store = TsStore(path or self.path, **kwargs)
        self.addCleanup(store.close)
        return store


def jittered_series(n, seed=0, interval=1000, jitter=50):
    """等间隔带抖动的时间戳 + 低分辨率示数（几十条不动偶尔跳）。"""
    rng = random.Random(seed)
    pairs = []
    ts = 1_700_000_000
    value = 20.00
    for _ in range(n):
        ts += interval + rng.randint(-jitter, jitter)
        if rng.random() < 1 / 40:
            value = round(value + rng.choice([0.25, -0.25, 0.5, 0.75]), 2)
        pairs.append((ts, value))
    return pairs


class TestRoundTrip(BlockCase):
    def test_small_block_round_trip(self):
        s = self.open(block_size=4)
        pairs = [(i * 3 + (i % 2), float(i % 5)) for i in range(23)]
        s.append_many(pairs)
        self.assertEqual(len(s), 23)
        self.assertEqual(s.read_all(), pairs)

    def test_reopen_and_continue(self):
        s = self.open(block_size=16)
        pairs = [(i, float(i)) for i in range(35)]
        s.append_many(pairs)
        s.close()
        again = self.open()
        self.assertEqual(again.read_all(), pairs)
        self.assertEqual(again.block_size, 16)
        self.assertEqual(again.last_ts, 34)
        again.append(35, 35.0)
        again.close()
        third = self.open()
        self.assertEqual(len(third), 36)
        self.assertEqual(third.read_at(-1), (35, 35.0))

    def test_exact_multiple_of_block_size(self):
        s = self.open(block_size=10)
        s.append_many([(i, float(i)) for i in range(30)])
        s.close()
        again = self.open()
        self.assertEqual(again.read_all(), [(i, float(i)) for i in range(30)])
        again.append(30, 30.0)
        self.assertEqual(again.read_at(30), (30, 30.0))

    def test_equal_and_negative_timestamps(self):
        s = self.open(block_size=4)
        s.append_many([(-7, 1.0), (-7, 2.0), (0, 0.0), (0, 0.0)])
        self.assertEqual(
            s.read_all(), [(-7, 1.0), (-7, 2.0), (0, 0.0), (0, 0.0)]
        )

    def test_int_value_reads_back_as_numeric_equal(self):
        s = self.open()
        s.append(1, 3)
        self.assertEqual(s.read_at(0), (1, 3))

    def test_bad_block_size_rejected(self):
        with self.assertRaises(ValueError):
            self.open(os.path.join(self._tmp.name, "b0"), block_size=0)
        with self.assertRaises(ValueError):
            self.open(os.path.join(self._tmp.name, "bm1"), block_size=-1)
        with self.assertRaises(TypeError):
            self.open(os.path.join(self._tmp.name, "bf"), block_size=1.5)

    def test_out_of_order_rejected_and_atomic(self):
        from tstore.errors import OutOfOrderError

        s = self.open(block_size=4)
        s.append(10, 1.0)
        with self.assertRaises(OutOfOrderError):
            s.append(9, 2.0)
        self.assertEqual(len(s), 1)
        with self.assertRaises(OutOfOrderError):
            s.append_many([(11, 1.0), (10, 1.0)])
        self.assertEqual(len(s), 1)


class TestCompressionRatio(BlockCase):
    def test_ten_thousand_points_under_five_bytes_each(self):
        pairs = jittered_series(10_000, seed=11)
        s = self.open(block_size=10_000)
        s.append_many(pairs)
        s.close()
        total = os.path.getsize(self.path)
        self.assertGreater(total, 0)
        self.assertLess(total, 5 * 10_000)
        again = self.open()
        self.assertEqual(again.read_all(), pairs)

    def test_measured_ratio_is_real_ratio(self):
        pairs = jittered_series(10_000, seed=12)
        s = self.open(block_size=10_000)
        s.append_many(pairs)
        s.close()
        raw_bytes = len(RAW_MAGIC) + 16 * 10_000
        ratio = os.path.getsize(self.path) / raw_bytes
        self.assertLess(ratio, 1 / 3)


class TestSingleBlockDecode(BlockCase):
    def test_read_at_decodes_only_one_block(self):
        s = self.open(block_size=100)
        s.append_many(jittered_series(1000, seed=3))
        self.assertEqual(s.stats()["decoded_blocks"], 0)
        s.read_at(550)
        self.assertEqual(s.stats()["decoded_blocks"], 1)
        s.read_at(250)
        self.assertEqual(s.stats()["decoded_blocks"], 2)
        s.read_at(251)
        self.assertEqual(s.stats()["decoded_blocks"], 3)

    def test_read_in_pending_tail_decodes_nothing(self):
        s = self.open(block_size=100)
        s.append_many(jittered_series(250, seed=4))
        s.read_at(201)
        self.assertEqual(s.stats()["decoded_blocks"], 0)

    def test_find_uses_header_binary_search(self):
        s = self.open(block_size=100)
        s.append_many(jittered_series(1000, seed=5))
        target = s.read_at(542)[0]
        idx = s.find(target)
        self.assertEqual(idx, 542)
        # 二分只翻块头，最多再解一个候选块看块内下标。
        self.assertLessEqual(s.stats()["decoded_blocks"], 2)

    def test_find_past_end_minus_one_without_scanning_payloads(self):
        s = self.open(block_size=100)
        s.append_many(jittered_series(1000, seed=6))
        self.assertEqual(s.find(10**18), -1)
        self.assertEqual(s.stats()["decoded_blocks"], 0)

    def test_duplicate_timestamp_returns_earliest(self):
        s = self.open(block_size=100)
        pairs = [(i // 3 * 10, float(i)) for i in range(500)]
        s.append_many(pairs)
        idx = s.find(100)
        self.assertEqual(pairs[idx][0], 100)
        self.assertEqual(pairs[idx - 1][0], 90)


class TestBadBlocks(BlockCase):
    def _three_block_file(self):
        s = self.open(block_size=100)
        s.append_many([(i, float(i % 7)) for i in range(250)])
        s.close()
        return self.path

    def _middle_block_payload_off(self, path):
        """第一整块之后，定位中间块块体的第 4 字节。"""
        with open(path, "rb") as fh:
            fh.seek(FILE_HEADER.size + 28)
            import struct
            payload_len = struct.unpack(">I", fh.read(4))[0]
        first_block_span = BLOCK_HEADER.size + payload_len
        return FILE_HEADER.size + first_block_span + BLOCK_HEADER.size + 3

    def test_crc_bad_middle_block_is_skipped(self):
        path = self._three_block_file()
        with open(path, "r+b") as fh:
            fh.seek(self._middle_block_payload_off(path))
            fh.write(b"\xff")
        s = self.open(path)
        st = s.stats()
        self.assertEqual(st["bad_blocks"], 1)
        self.assertEqual(len(s), 150)
        # 好块紧凑下标：第一块 0..99，尾块 200..249 从 100 起。
        self.assertEqual(s.read_at(0), (0, 0.0))
        self.assertEqual(s.read_at(100), (200, 200.0 % 7))
        self.assertEqual(list(s)[:2], [(0, 0.0), (1, 1.0)])
        self.assertEqual(len(list(s)), 150)

    def test_find_skips_bad_block(self):
        path = self._three_block_file()
        with open(path, "r+b") as fh:
            fh.seek(self._middle_block_payload_off(path))
            fh.write(b"\xff")
        s = self.open(path)
        # 坏块剔除，紧凑下标：第一块 0..99，好尾块 200..249 从 100 起。
        self.assertEqual(s.find(200), 100)
        self.assertEqual(s.find(150), 100)
        self.assertEqual(s.find(250), -1)

    def test_truncated_payload_tail_is_dropped(self):
        path = self._three_block_file()
        full = os.path.getsize(path)
        with open(path, "r+b") as fh:
            fh.truncate(full - 17)
        s = self.open(path)
        self.assertEqual(s.stats()["bad_blocks"], 1)
        self.assertEqual(len(s), 200)
        s.append(250, 9.0)
        s.close()
        again = self.open(path)
        self.assertEqual(len(again), 201)
        self.assertEqual(again.read_at(-1), (250, 9.0))

    def test_truncated_header_tail_is_dropped(self):
        path = self._three_block_file()
        import struct

        with open(path, "rb") as fh:
            off = FILE_HEADER.size
            fh.seek(off + 28)
            first = BLOCK_HEADER.size + struct.unpack(">I", fh.read(4))[0]
            fh.seek(off + first + 28)
            second = BLOCK_HEADER.size + struct.unpack(">I", fh.read(4))[0]
        with open(path, "r+b") as fh:
            fh.truncate(FILE_HEADER.size + first + second + 7)
        s = self.open(path)
        self.assertEqual(s.stats()["bad_blocks"], 1)
        self.assertEqual(len(s), 200)

    def test_bad_marker_tail_does_not_whole_store(self):
        path = self._three_block_file()
        full = os.path.getsize(path)
        with open(path, "r+b") as fh:
            fh.seek(full - BLOCK_HEADER.size)
            fh.write(b"GARBAGE!")
        s = self.open(path)
        self.assertEqual(s.stats()["bad_blocks"], 1)
        self.assertEqual(len(s), 200)

    def test_append_after_bad_block_and_reread(self):
        path = self._three_block_file()
        with open(path, "r+b") as fh:
            fh.seek(self._middle_block_payload_off(path))
            fh.write(b"\xff")
        s = self.open(path)
        s.append(300, 3.0)
        s.close()
        again = self.open(path)
        self.assertEqual(again.stats()["bad_blocks"], 1)
        self.assertEqual(again.read_at(-1), (300, 3.0))


class TestLegacyCompat(BlockCase):
    def _legacy_file(self):
        path = os.path.join(self._tmp.name, "legacy.ts")
        with open(path, "wb") as fh:
            fh.write(RAW_MAGIC)
            for ts, value in [(100, 1.5), (100, 2.5), (105, 3.5)]:
                fh.write(struct.pack("<qd", ts, value))
        return path

    def test_legacy_file_stays_raw_after_append(self):
        path = self._legacy_file()
        s = self.open(path)
        self.assertIsNone(s.block_size)
        s.append(200, 9.5)
        s.close()
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(len(RAW_MAGIC)), RAW_MAGIC)
        self.assertEqual(os.path.getsize(path), len(RAW_MAGIC) + 4 * 16)
        again = self.open(path)
        self.assertEqual(
            again.read_all(),
            [(100, 1.5), (100, 2.5), (105, 3.5), (200, 9.5)],
        )
        self.assertEqual(again.find(150), 3)

    def test_unknown_magic_still_rejected(self):
        path = os.path.join(self._tmp.name, "bad.ts")
        with open(path, "wb") as fh:
            fh.write(b"NOTAMAG\n" + b"\x00" * 16)
        with self.assertRaises(TsFormatError):
            TsStore(path)


def _reference_find(pairs, ts):
    for i, (cur, _) in enumerate(pairs):
        if cur >= ts:
            return i
    return -1


class TestFuzzAgainstRaw(BlockCase):
    def _run_fuzz(self, seed, block_size):
        rng = random.Random(seed)
        block_path = os.path.join(self._tmp.name, "blk_%d" % seed)
        raw_path = os.path.join(self._tmp.name, "raw_%d" % seed)
        with open(raw_path, "wb") as fh:
            fh.write(RAW_MAGIC)
        bs = TsStore(block_path, block_size=block_size)
        raw = RawStore(raw_path)
        reference = []

        for phase in range(8):
            n = rng.randrange(0, 50)
            cur = reference[-1][0] if reference else rng.randrange(-100, 100)
            batch = []
            for _ in range(n):
                cur += rng.choice([0, 0, 0, 1, 2, 5])
                value = rng.choice(
                    [1.0, 1.0, 2.5, -3.25, 0.0, 100.5, 2,
                     float(rng.randrange(20))]
                )
                batch.append((cur, value))
            bs.append_many(batch)
            raw.append_many(batch)
            reference.extend(batch)

            if reference and rng.random() < 0.7:
                i = rng.randrange(len(reference))
                self.assertEqual(bs.read_at(i), raw.read_at(i))
            if reference and rng.random() < 0.7:
                target = rng.choice(
                    [
                        reference[0][0] - 1,
                        reference[rng.randrange(len(reference))][0],
                        reference[-1][0] + 7,
                    ]
                )
                self.assertEqual(bs.find(target), _reference_find(reference, target))
            if rng.random() < 0.3:
                self.assertEqual(len(bs), len(reference))
            if rng.random() < 0.3:
                self.assertEqual(bs.last_ts, reference[-1][0] if reference else None)

        if rng.random() < 0.6:
            bs.close()
            raw.close()
            bs = TsStore(block_path)
            raw = RawStore(raw_path)
            self.assertEqual(bs.read_all(), reference)

        self.assertEqual(bs.stats()["bad_blocks"], 0)
        bs.close()
        raw.close()

    def test_fuzz_various_block_sizes_and_seeds(self):
        for seed, size in [(1, 1), (2, 2), (3, 7), (4, 64), (5, 128),
                           (6, 1000), (7, 10000)]:
            self._run_fuzz(seed, size)

    def test_fuzz_single_appends_match_raw(self):
        rng = random.Random(99)
        block_path = os.path.join(self._tmp.name, "blk_single")
        raw_path = os.path.join(self._tmp.name, "raw_single")
        with open(raw_path, "wb") as fh:
            fh.write(RAW_MAGIC)
        bs = TsStore(block_path, block_size=13)
        raw = RawStore(raw_path)
        cur = 0
        for _ in range(400):
            cur += rng.choice([0, 1, 3])
            value = rng.choice([rng.randrange(50) * 0.5, 7.0, 7.0])
            bs.append(cur, value)
            raw.append(cur, value)
        self.assertEqual(bs.read_all(), raw.read_all())
        bs.close()
        raw.close()


@unittest.skipUnless(os.environ.get("TSTORE_SLOW"), "设 TSTORE_SLOW=1 跑百万级性能红线")
class TestPerformance(BlockCase):
    N = 1_000_000

    def _series(self, seed):
        rng = random.Random(seed)
        ts = 1_700_000_000_000
        value = 20.00
        out = []
        for _ in range(self.N):
            ts += 1000 + rng.randint(-50, 50)
            if rng.random() < 1 / 40:
                value = round(value + rng.choice([0.25, -0.25, 0.5, 0.75]), 2)
            out.append((ts, value))
        return out

    def test_million_writes_and_random_reads(self):
        pairs = self._series(1)
        started = time.perf_counter()
        s = self.open(block_size=10_000)
        for off in range(0, len(pairs), 50_000):
            s.append_many(pairs[off:off + 50_000])
        s.close()
        write_elapsed = time.perf_counter() - started
        self.assertLess(write_elapsed, 60.0)

        size = os.path.getsize(self.path)
        self.assertLess(size / self.N, 5.0)

        s = self.open()
        rng = random.Random(2)
        started = time.perf_counter()
        for _ in range(1000):
            s.read_at(rng.randrange(self.N))
        read_elapsed = time.perf_counter() - started
        self.assertLess(read_elapsed, 10.0)
        # 每次随机读只解一块，库再大也不许涨。
        self.assertEqual(s.stats()["decoded_blocks"], 1000)

    def test_read_cost_does_not_grow_with_hundred_x_store(self):
        small = self._series(3)[:10_000]
        small_path = os.path.join(self._tmp.name, "small.blk")
        with TsStore(small_path, block_size=10_000) as store:
            store.append_many(small)

        pairs = self._series(4)[:1_000_000]
        big = self.open(block_size=10_000)
        for off in range(0, len(pairs), 50_000):
            big.append_many(pairs[off:off + 50_000])

        with TsStore(small_path) as small_store:
            rng = random.Random(5)
            small_indices = [rng.randrange(10_000) for _ in range(100)]
            started = time.perf_counter()
            for i in small_indices:
                small_store.read_at(i)
            small_elapsed = time.perf_counter() - started
            self.assertEqual(small_store.stats()["decoded_blocks"], 100)

            rng = random.Random(6)
            big_indices = [rng.randrange(self.N) for _ in range(100)]
            started = time.perf_counter()
            for i in big_indices:
                big.read_at(i)
            big_elapsed = time.perf_counter() - started
            self.assertEqual(big.stats()["decoded_blocks"], 100)
            # 同样 100 次、每次只解一块，库大 100 倍耗时不该随库变大。
            self.assertLess(big_elapsed, max(2.0, small_elapsed * 10))


if __name__ == "__main__":
    unittest.main()
