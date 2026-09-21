"""块压缩格式的行为、压缩率、坏块容错与性能测试。"""  # 裸存基线见 test_store.py

import os
import random
import struct
import tempfile
import time
import unittest

from tstore import TsStore
from tstore.blocks import BLOCK_HEADER
from tstore.blockstore import BLK_MAGIC
from tstore.errors import OutOfOrderError
from tstore.layout import HEADER as RAW_HEADER


def jittered_points(n, seed=1):
    """等间隔带抖动的时间戳，值像低分辨率示数：几十条不动偶尔跳。"""
    rng = random.Random(seed)
    pairs = []
    ts = 1700000000
    value = 20.0
    for _ in range(n):
        ts += 1000 + rng.randint(-3, 3)
        if rng.random() < 0.03:
            value = round(value + rng.choice([-0.5, -0.25, 0.25, 0.5]), 2)
        pairs.append((ts, value))
    return pairs


class BlockCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "points.ts")

    def make_store(self, path=None, **kwargs):
        store = TsStore(path or self.path, **kwargs)
        self.addCleanup(store.close)
        return store

    def fill(self, pairs, **kwargs):
        store = self.make_store(**kwargs)
        store.append_many(pairs)
        return store

    def block_spans(self, path):
        """按块头把文件走一遍，返回 [(偏移, 条数, 负载长度)]。"""
        spans = []
        with open(path, "rb") as fh:
            data = fh.read()
        offset = len(BLK_MAGIC)
        while offset < len(data):
            _, _, count, plen, _ = BLOCK_HEADER.unpack(
                data[offset : offset + BLOCK_HEADER.size]
            )
            spans.append((offset, count, plen))
            offset += BLOCK_HEADER.size + plen
        return spans


class TestFormat(BlockCase):
    def test_new_file_uses_block_magic(self):
        self.make_store().close()
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(len(BLK_MAGIC)), BLK_MAGIC)

    def test_block_size_configurable(self):
        s = self.fill(jittered_points(10), block_size=4)
        s.close()
        spans = self.block_spans(self.path)
        self.assertEqual([count for _, count, _ in spans], [4, 4, 2])
        again = self.make_store()
        self.assertEqual(len(again), 10)

    def test_roundtrip_after_reopen(self):
        pairs = jittered_points(1000)
        self.fill(pairs, block_size=64).close()
        again = self.make_store()
        self.assertEqual(again.read_all(), pairs)
        self.assertEqual(again.last_ts, pairs[-1][0])

    def test_stats_has_block_counters(self):
        s = self.fill(jittered_points(10))
        st = s.stats()
        self.assertEqual(st["blocks_decoded"], 0)
        self.assertEqual(st["bad_blocks"], [])


class TestCompression(BlockCase):
    def test_ten_thousand_points_under_five_bytes_each(self):
        pairs = jittered_points(10000)
        self.fill(pairs).close()
        size = os.path.getsize(self.path)
        per_record = size / len(pairs)
        self.assertLess(
            per_record,
            5.0,
            "平均每条 %.2f 字节（%d 条共 %d 字节），应压到 5 字节内"
            % (per_record, len(pairs), size),
        )
        again = self.make_store()
        self.assertEqual(again.read_all(), pairs)


class TestRandomAccess(BlockCase):
    def test_read_at_decodes_only_its_block(self):
        s = self.fill(jittered_points(1000), block_size=64)
        before = s.stats()["blocks_decoded"]
        s.read_at(500)
        self.assertEqual(s.stats()["blocks_decoded"] - before, 1)
        s.read_at(501)  # 同一块，命中缓存不再解
        self.assertEqual(s.stats()["blocks_decoded"] - before, 1)
        s.read_at(700)  # 另一块，再解一块
        self.assertEqual(s.stats()["blocks_decoded"] - before, 2)

    def test_find_decodes_at_most_one_block(self):
        pairs = jittered_points(1000)
        s = self.fill(pairs, block_size=64)
        before = s.stats()["blocks_decoded"]
        self.assertEqual(s.find(pairs[500][0]), 500)
        self.assertLessEqual(s.stats()["blocks_decoded"] - before, 1)

    def test_find_duplicates_across_blocks_returns_earliest(self):
        pairs = [(10, 1.0)] * 6 + [(20, 2.0)] * 6
        s = self.fill(pairs, block_size=4)
        self.assertEqual(s.find(10), 0)
        self.assertEqual(s.find(15), 6)
        self.assertEqual(s.find(20), 6)
        self.assertEqual(s.find(21), -1)

    def test_pending_visible_before_flush(self):
        s = self.fill(jittered_points(5), block_size=100)
        self.assertEqual(len(s), 5)
        self.assertEqual(s.read_at(4), s.read_all()[4])
        self.assertEqual(s.find(s.last_ts), 4)


class TestBadBlocks(BlockCase):
    def corrupt_byte(self, offset):
        with open(self.path, "r+b") as fh:
            fh.seek(offset)
            byte = fh.read(1)
            fh.seek(offset)
            fh.write(bytes([byte[0] ^ 0xFF]))

    def test_corrupt_payload_block_skipped(self):
        pairs = jittered_points(20, seed=2)
        self.fill(pairs, block_size=4).close()
        offset, count, _ = self.block_spans(self.path)[2]
        self.corrupt_byte(offset + BLOCK_HEADER.size)
        s = self.make_store()
        self.assertEqual(s.stats()["bad_blocks"], [2])
        self.assertEqual(len(s), 16)
        self.assertEqual(s.read_all(), pairs[:8] + pairs[12:])
        self.assertEqual(s.read_at(7), pairs[7])
        self.assertEqual(s.read_at(8), pairs[12])
        self.assertEqual(s.find(pairs[12][0]), 8)

    def test_corrupt_header_field_block_skipped(self):
        pairs = jittered_points(12, seed=3)
        self.fill(pairs, block_size=4).close()
        offset, _, _ = self.block_spans(self.path)[1]
        self.corrupt_byte(offset)  # 基准时间被改，CRC 一样不过
        s = self.make_store()
        self.assertEqual(s.stats()["bad_blocks"], [1])
        self.assertEqual(s.read_all(), pairs[:4] + pairs[8:])

    def test_truncated_tail_block_skipped(self):
        pairs = jittered_points(20, seed=4)
        self.fill(pairs, block_size=4).close()
        spans = self.block_spans(self.path)
        cut = spans[-1][0] + BLOCK_HEADER.size + 2
        with open(self.path, "r+b") as fh:
            fh.truncate(cut)
        s = self.make_store()
        self.assertEqual(s.stats()["bad_blocks"], [4])
        self.assertEqual(s.read_all(), pairs[:16])
        s.append(pairs[16][0], 9.0)  # 坏尾巴之后照样能追加
        self.assertEqual(s.read_at(-1), (pairs[16][0], 9.0))

    def test_all_blocks_bad_still_opens(self):
        self.fill(jittered_points(8, seed=5), block_size=4).close()
        for offset, _, _ in self.block_spans(self.path):
            self.corrupt_byte(offset + BLOCK_HEADER.size)
        s = self.make_store()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.stats()["bad_blocks"], [0, 1])
        s.append(1, 1.0)
        self.assertEqual(s.read_all(), [(1, 1.0)])


class TestDifferential(BlockCase):
    def make_raw_store(self, name="raw.ts"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(RAW_HEADER)
        store = TsStore(path)
        self.addCleanup(store.close)
        return store

    def test_random_ops_match_raw_store(self):
        rng = random.Random(99)
        block = self.make_store(block_size=rng.choice([1, 7, 64]))
        raw = self.make_raw_store()
        ts = rng.randint(-100, 100)
        for _ in range(300):
            op = rng.random()
            if op < 0.55:
                batch = []
                for _ in range(rng.randint(1, 20)):
                    ts += rng.choice([0, 0, 1, 1, 2, 5, 17])
                    value = rng.choice(
                        [0, 1, -3, 0.5, 20.25, rng.random() * 100, -rng.random()]
                    )
                    batch.append((ts, value))
                block.append_many(batch)
                raw.append_many(batch)
            elif op < 0.75:
                if len(block):
                    index = rng.randrange(-len(block), len(block))
                    self.assertEqual(block.read_at(index), raw.read_at(index))
            elif op < 0.9:
                target = ts + rng.randint(-200, 200)
                self.assertEqual(block.find(target), raw.find(target))
            else:
                self.assertEqual(len(block), len(raw))
                self.assertEqual(block.last_ts, raw.last_ts)
        self.assertEqual(block.read_all(), raw.read_all())
        expected = raw.read_all()
        block.close()
        raw.close()
        self.assertEqual(self.make_store().read_all(), expected)

    def test_out_of_order_still_rejected(self):
        s = self.fill(jittered_points(300), block_size=16)
        with self.assertRaises(OutOfOrderError):
            s.append(s.last_ts - 1, 0.0)
        with self.assertRaises(OutOfOrderError):
            s.append_many([(s.last_ts, 1.0), (s.last_ts - 1, 2.0)])
        self.assertEqual(len(s), 300)


class TestLegacyCompat(BlockCase):
    def test_append_to_legacy_keeps_raw_layout(self):
        path = os.path.join(self._tmp.name, "legacy.ts")
        with open(path, "wb") as fh:
            fh.write(RAW_HEADER + struct.pack("<qd", 100, 1.5))
        s = self.make_store(path=path)
        s.append(105, 2.5)
        s.close()
        self.assertEqual(os.path.getsize(path), len(RAW_HEADER) + 2 * 16)
        again = self.make_store(path=path)
        self.assertEqual(again.read_all(), [(100, 1.5), (105, 2.5)])
        self.assertEqual(again.stats()["blocks_decoded"], 0)


class TestPerformance(BlockCase):
    def test_million_writes_and_random_reads(self):
        pairs = jittered_points(1000000, seed=11)
        started = time.time()
        s = self.make_store()
        s.append_many(pairs)
        self.assertLess(time.time() - started, 60, "百万条写入超过一分钟")
        s.close()

        rng = random.Random(21)
        s = self.make_store()
        started = time.time()
        for _ in range(1000):
            index = rng.randrange(len(pairs))
            before = s.stats()["blocks_decoded"]
            self.assertEqual(s.read_at(index), pairs[index])
            self.assertLessEqual(
                s.stats()["blocks_decoded"] - before, 1, "单次读解块数不许涨"
            )
        self.assertLess(time.time() - started, 10, "一千次随机访问超过十秒")


if __name__ == "__main__":
    unittest.main()
