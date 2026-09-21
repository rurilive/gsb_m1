"""transfer 模块的行为测试：块仓、增量传输、断点续传与资源占用。"""

import json
import os
import random
import threading
import tracemalloc
import unittest
from unittest import mock

from snapwire.hashing import hash_bytes
from snapwire.sync import Channel, ChannelBroken, sync_full
from snapwire.transfer import BlockIndex, Receiver, Sender


def drive(sender, receiver, manifest, dst):
    """推进传输直到 dst 落盘；通道中断先把已送达的块收进仓再抛。"""
    while True:
        try:
            if receiver.apply(manifest, dst):
                return
            sender.push(manifest)
        except ChannelBroken:
            try:
                receiver.apply(manifest, dst)
            except ChannelBroken:
                pass
            raise


class RecordingChannel(Channel):
    """记下每一帧的通道，供测试检查请求与块帧。"""

    def __init__(self, limit=None):
        super().__init__(limit=limit)
        self.sent = []

    def send(self, frame):
        super().send(frame)
        self.sent.append(bytes(frame))

    def requests(self):
        return [json.loads(f[4:].decode("ascii"))
                for f in self.sent if f.startswith(b"REQ ")]

    def blocks(self):
        return [f for f in self.sent if f.startswith(b"BLK ")]


class CorruptOnceChannel(Channel):
    """把第一帧块数据改坏一个字节，模拟线路噪声。"""

    def __init__(self):
        super().__init__()
        self.corrupted = 0

    def send(self, frame):
        if frame.startswith(b"BLK ") and not self.corrupted:
            self.corrupted += 1
            frame = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        super().send(frame)


class TransferCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def path(self, name):
        return os.path.join(self.root, name)

    def write(self, name, data):
        path = self.path(name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def read(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def temp_files(self):
        return [n for n in os.listdir(self.root) if n.startswith(".snapwire-")]


class TestBlockIndex(TransferCase):
    def test_put_get_has_roundtrip(self):
        index = BlockIndex(64)
        digest = index.put(b"hello")
        self.assertEqual(digest, hash_bytes(b"hello"))
        self.assertTrue(index.has(digest))
        self.assertEqual(index.get(digest), b"hello")
        self.assertFalse(index.has(hash_bytes(b"other")))

    def test_same_content_stored_once(self):
        index = BlockIndex(64)
        first = index.put(b"same")
        second = index.put(b"same")
        self.assertEqual(first, second)
        self.assertEqual(index.stats(), {"blocks": 1, "bytes": 4})

    def test_stats_counts_blocks_and_bytes(self):
        index = BlockIndex(64)
        index.put(b"aa")
        index.put(b"bbb")
        self.assertEqual(index.stats(), {"blocks": 2, "bytes": 5})

    def test_get_missing_raises_key_error(self):
        with self.assertRaises(KeyError):
            BlockIndex(64).get(hash_bytes(b"nope"))

    def test_bad_block_size_rejected(self):
        with self.assertRaises(ValueError):
            BlockIndex(0)


class TestPlan(TransferCase):
    def test_manifest_lists_per_block_digests(self):
        data = random.Random(1).randbytes(1000)
        src = self.write("a.bin", data)
        sender = Sender(BlockIndex(256), Channel())
        manifest = sender.plan(src)
        expect = [hash_bytes(data[i:i + 256]) for i in range(0, 1000, 256)]
        self.assertEqual(manifest["blocks"], expect)
        self.assertEqual(manifest["size"], 1000)
        self.assertEqual(manifest["block_size"], 256)

    def test_empty_file_has_no_blocks(self):
        src = self.write("empty.bin", b"")
        manifest = Sender(BlockIndex(64), Channel()).plan(src)
        self.assertEqual(manifest["blocks"], [])
        self.assertEqual(manifest["size"], 0)

    def test_plan_peak_memory_does_not_grow_with_file(self):
        rng = random.Random(7)
        small = self.write("small.bin", rng.randbytes(1 << 18))
        big = self.write("big.bin", rng.randbytes(1 << 23))
        sender = Sender(BlockIndex(1 << 16), Channel())
        tracemalloc.start()
        try:
            sender.plan(small)
            peak_small = tracemalloc.get_traced_memory()[1]
            tracemalloc.reset_peak()
            sender.plan(big)
            peak_big = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLess(peak_big, peak_small + (1 << 19))


class TestRoundTrip(TransferCase):
    def sync(self, src, dst, block=1024, s_index=None, r_index=None,
             channel=None):
        channel = channel or Channel()
        sender = Sender(s_index or BlockIndex(block), channel)
        receiver = Receiver(r_index or BlockIndex(block), channel)
        manifest = sender.plan(src)
        drive(sender, receiver, manifest, dst)
        return channel

    def test_full_transfer_matches_source(self):
        data = random.Random(2).randbytes(10000)
        src = self.write("src.bin", data)
        dst = self.path("dst.bin")
        self.sync(src, dst)
        self.assertEqual(self.read(dst), data)

    def test_empty_file(self):
        src = self.write("empty.bin", b"")
        dst = self.path("dst-empty.bin")
        channel = self.sync(src, dst)
        self.assertEqual(self.read(dst), b"")
        self.assertEqual(channel.bytes_moved, 0)

    def test_partial_last_block(self):
        block = 512
        data = random.Random(3).randbytes(3 * block + 17)
        src = self.write("part.bin", data)
        dst = self.path("part-out.bin")
        self.sync(src, dst, block=block)
        self.assertEqual(self.read(dst), data)

    def test_random_edits_match_sync_full_byte_for_byte(self):
        rng = random.Random(99)
        block = 1024
        data = bytearray(rng.randbytes(200 * 1024))
        src = self.write("src.bin", bytes(data))
        dst_inc = self.path("inc.bin")
        dst_full = self.path("full.bin")
        s_index, r_index = BlockIndex(block), BlockIndex(block)
        for _ in range(6):
            pos = rng.randrange(len(data))
            data[pos:pos + rng.randrange(1, 3000)] = rng.randbytes(
                rng.randrange(1, 3000))
            self.write("src.bin", bytes(data))
            channel = Channel()
            sender = Sender(s_index, channel)
            receiver = Receiver(r_index, channel)
            drive(sender, receiver, sender.plan(src), dst_inc)
            sync_full(src, dst_full, Channel())
            self.assertEqual(self.read(dst_inc), self.read(dst_full))
            self.assertEqual(self.read(dst_inc), bytes(data))

    def test_small_edit_moves_only_changed_blocks(self):
        rng = random.Random(4)
        block = 4096
        data = bytearray(rng.randbytes(1 << 20))
        src = self.write("big.bin", bytes(data))
        dst = self.path("big-out.bin")
        s_index, r_index = BlockIndex(block), BlockIndex(block)
        self.sync(src, dst, block=block, s_index=s_index, r_index=r_index)
        data[500000:500100] = b"x" * 100
        self.write("big.bin", bytes(data))
        channel = Channel()
        sender = Sender(s_index, channel)
        receiver = Receiver(r_index, channel)
        drive(sender, receiver, sender.plan(src), dst)
        self.assertEqual(self.read(dst), bytes(data))
        self.assertLess(channel.bytes_moved, 4 * block)

    def test_repeated_blocks_stored_once_and_reused_across_files(self):
        block = 256
        shared = random.Random(5).randbytes(block)
        data_a = shared * 4 + b"a" * block
        data_b = shared * 2 + b"b" * block
        src_a = self.write("a.bin", data_a)
        src_b = self.write("b.bin", data_b)
        r_index = BlockIndex(block)
        self.sync(src_a, self.path("a-out.bin"), block=block, r_index=r_index)
        channel = self.sync(src_b, self.path("b-out.bin"), block=block,
                            r_index=r_index)
        self.assertEqual(self.read(self.path("b-out.bin")), data_b)
        self.assertEqual(r_index.stats()["blocks"], 3)
        self.assertLess(channel.bytes_moved, 2 * block + 1024)

    def test_up_to_date_dst_is_not_rewritten(self):
        data = random.Random(6).randbytes(5000)
        src = self.write("src.bin", data)
        dst = self.path("dst.bin")
        r_index = BlockIndex(1024)
        channel = Channel()
        sender = Sender(BlockIndex(1024), channel)
        receiver = Receiver(r_index, channel)
        manifest = sender.plan(src)
        drive(sender, receiver, manifest, dst)
        before = os.stat(dst)
        channel2 = Channel()
        receiver2 = Receiver(r_index, channel2)
        self.assertTrue(receiver2.apply(manifest, dst))
        after = os.stat(dst)
        self.assertEqual((before.st_ino, before.st_mtime_ns),
                         (after.st_ino, after.st_mtime_ns))
        self.assertEqual(channel2.bytes_moved, 0)


class TestResilience(TransferCase):
    def test_interrupted_transfer_resumes_without_resending(self):
        block = 512
        data = random.Random(8).randbytes(10 * block)
        src = self.write("src.bin", data)
        dst = self.path("dst.bin")
        s_index, r_index = BlockIndex(block), BlockIndex(block)
        leg1 = RecordingChannel(limit=3000)
        sender = Sender(s_index, leg1)
        receiver = Receiver(r_index, leg1)
        manifest = sender.plan(src)
        with self.assertRaises(ChannelBroken):
            drive(sender, receiver, manifest, dst)
        self.assertFalse(os.path.exists(dst))
        confirmed = r_index.stats()["blocks"]
        self.assertGreater(confirmed, 0)
        self.assertLess(confirmed, 10)

        leg2 = RecordingChannel()
        sender2 = Sender(s_index, leg2)
        receiver2 = Receiver(r_index, leg2)
        drive(sender2, receiver2, manifest, dst)
        self.assertEqual(self.read(dst), data)
        sent_digests = set()
        for frame in leg1.blocks() + leg2.blocks():
            digest = frame.split(b" ", 2)[1].decode("ascii")
            self.assertNotIn(digest, sent_digests, "块被重传了")
            sent_digests.add(digest)
        self.assertEqual(len(sent_digests), 10)
        self.assertLess(leg2.bytes_moved,
                        (10 - confirmed) * (block + 80) + 1024)

    def test_corrupt_block_is_re_requested_alone(self):
        block = 1024
        data = random.Random(9).randbytes(4 * block)
        src = self.write("src.bin", data)
        dst = self.path("dst.bin")

        class NoisyChannel(CorruptOnceChannel):
            def __init__(self):
                super().__init__()
                self.frames = []

            def send(self, frame):
                self.frames.append(bytes(frame))
                super().send(frame)

        channel = NoisyChannel()
        sender = Sender(BlockIndex(block), channel)
        receiver = Receiver(BlockIndex(block), channel)
        drive(sender, receiver, sender.plan(src), dst)
        self.assertEqual(self.read(dst), data)
        self.assertEqual(channel.corrupted, 1)
        requests = [json.loads(f[4:].decode("ascii"))
                    for f in channel.frames if f.startswith(b"REQ ")]
        self.assertEqual(len(requests[0]), 4)
        self.assertEqual(len(requests[1]), 1)
        bad = requests[1][0]
        blocks = [f for f in channel.frames if f.startswith(b"BLK ")]
        self.assertEqual(len(blocks), 5)
        self.assertEqual(blocks[-1].split(b" ", 2)[1].decode("ascii"), bad)

    def test_failed_rebuild_leaves_no_partial_file(self):
        block = 256
        data = random.Random(10).randbytes(4 * block)
        src = self.write("src.bin", data)
        dst = self.write("dst.bin", b"old content")
        r_index = BlockIndex(block)
        for i in range(0, len(data), block):
            r_index.put(data[i:i + block])
        manifest = Sender(BlockIndex(block), Channel()).plan(src)
        receiver = Receiver(r_index, Channel())
        with mock.patch("snapwire.transfer.os.replace",
                        side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                receiver.apply(manifest, dst)
        self.assertEqual(self.read(dst), b"old content")
        self.assertEqual(self.temp_files(), [])

    def test_concurrent_writers_never_leave_half_file(self):
        block = 512
        data_a = random.Random(11).randbytes(8 * block)
        data_b = random.Random(12).randbytes(8 * block)
        src_a = self.write("a.bin", data_a)
        src_b = self.write("b.bin", data_b)
        dst = self.path("shared.bin")
        errors = []

        def work(src):
            try:
                channel = Channel()
                sender = Sender(BlockIndex(block), channel)
                receiver = Receiver(BlockIndex(block), channel)
                drive(sender, receiver, sender.plan(src), dst)
            except Exception as exc:  # pragma: no cover - 失败时统一上报
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(src,))
                   for src in (src_a, src_b, src_a, src_b)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertIn(self.read(dst), (data_a, data_b))
        self.assertEqual(self.temp_files(), [])


class TestMemory(TransferCase):
    def test_rebuild_peak_memory_bounded_by_block_size(self):
        block = 1 << 16
        data = random.Random(13).randbytes(4 << 20)
        src = self.write("src.bin", data)
        r_index = BlockIndex(block)
        digests = [r_index.put(data[i:i + block])
                   for i in range(0, len(data), block)]
        manifest = Sender(BlockIndex(block), Channel()).plan(src)
        self.assertEqual(manifest["blocks"], digests)
        dst = self.path("dst.bin")
        receiver = Receiver(r_index, Channel())
        tracemalloc.start()
        try:
            self.assertTrue(receiver.apply(manifest, dst))
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(self.read(dst), data)
        self.assertLess(peak, 4 * block)

    def test_channel_never_holds_whole_file(self):
        block = 1024
        data = random.Random(14).randbytes(200 * block)
        src = self.write("src.bin", data)
        dst = self.path("dst.bin")
        channel = Channel()
        sender = Sender(BlockIndex(block), channel)
        receiver = Receiver(BlockIndex(block), channel)
        manifest = sender.plan(src)
        peak_pending = 0
        while not receiver.apply(manifest, dst):
            sender.push(manifest)
            peak_pending = max(peak_pending, channel.pending())
        self.assertEqual(self.read(dst), data)
        self.assertLessEqual(peak_pending, 16)


if __name__ == "__main__":
    unittest.main()
