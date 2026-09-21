"""sync 模块现有行为的锁定测试。"""

import os
import tempfile
import unittest

from snapwire.sync import Channel, ChannelBroken, sync_full


class TestChannel(unittest.TestCase):
    def test_recv_follows_send_order(self):
        channel = Channel()
        channel.send(b"one")
        channel.send(b"two")
        self.assertEqual(channel.pending(), 2)
        self.assertEqual(channel.recv(), b"one")
        self.assertEqual(channel.recv(), b"two")
        self.assertEqual(channel.pending(), 0)

    def test_bytes_moved_counts_everything_sent(self):
        channel = Channel()
        self.assertEqual(channel.bytes_moved, 0)
        channel.send(b"abcd")
        channel.send(b"ef")
        self.assertEqual(channel.bytes_moved, 6)

    def test_recv_on_empty_channel_raises(self):
        channel = Channel()
        with self.assertRaises(ChannelBroken):
            channel.recv()

    def test_limit_is_inclusive(self):
        channel = Channel(limit=6)
        channel.send(b"abc")
        channel.send(b"def")
        self.assertEqual(channel.bytes_moved, 6)
        self.assertFalse(channel.broken)

    def test_send_beyond_limit_breaks_and_keeps_delivered_frames(self):
        channel = Channel(limit=6)
        channel.send(b"abc")
        with self.assertRaises(ChannelBroken):
            channel.send(b"defg")
        self.assertTrue(channel.broken)
        self.assertEqual(channel.bytes_moved, 3)
        self.assertEqual(channel.recv(), b"abc")

    def test_broken_channel_refuses_further_sends(self):
        channel = Channel(limit=0)
        with self.assertRaises(ChannelBroken):
            channel.send(b"x")
        with self.assertRaises(ChannelBroken):
            channel.send(b"")

    def test_drain_takes_all_pending_frames(self):
        channel = Channel()
        channel.send(b"a")
        channel.send(b"bb")
        self.assertEqual(channel.drain(), [b"a", b"bb"])
        self.assertEqual(channel.pending(), 0)


class TestSyncFull(unittest.TestCase):
    def setUp(self):
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

    def test_copies_content_and_reports_bytes(self):
        data = bytes(range(256)) * 40
        src = self.write("src.bin", data)
        dst = self.path("out/dst.bin")
        channel = Channel()
        moved = sync_full(src, dst, channel, chunk_size=1024)
        self.assertEqual(self.read(dst), data)
        self.assertEqual(moved, len(data))
        self.assertEqual(channel.bytes_moved, len(data))

    def test_empty_file(self):
        src = self.write("empty.bin", b"")
        dst = self.path("empty-copy.bin")
        channel = Channel()
        moved = sync_full(src, dst, channel)
        self.assertEqual(self.read(dst), b"")
        self.assertEqual(moved, 0)

    def test_overwrites_existing_destination(self):
        src = self.write("src.bin", b"new content")
        dst = self.write("dst.bin", b"stale content that is longer")
        channel = Channel()
        sync_full(src, dst, channel)
        self.assertEqual(self.read(dst), b"new content")

    def test_bytes_moved_delta_not_total(self):
        src = self.write("src.bin", b"x" * 100)
        channel = Channel()
        channel.send(b"warmup")
        moved = sync_full(src, self.path("dst.bin"), channel, chunk_size=30)
        self.assertEqual(moved, 100)
        self.assertEqual(channel.bytes_moved, 106)

    def test_interruption_propagates(self):
        src = self.write("src.bin", b"y" * 100)
        channel = Channel(limit=50)
        with self.assertRaises(ChannelBroken):
            sync_full(src, self.path("dst.bin"), channel, chunk_size=30)
        self.assertEqual(channel.bytes_moved, 30)
        self.assertTrue(channel.broken)

    def test_invalid_chunk_size_raises(self):
        src = self.write("src.bin", b"z")
        channel = Channel()
        with self.assertRaises(ValueError):
            sync_full(src, self.path("dst.bin"), channel, chunk_size=0)


if __name__ == "__main__":
    unittest.main()
