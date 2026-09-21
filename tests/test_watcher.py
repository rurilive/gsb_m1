"""Watcher 现有行为的锁定测试。"""

import os
import tempfile
import unittest

from snapwatch import Event, ManualClock, SysFS, Watcher


def make_file(root, rel, data, clock, stamp=None):
    """写一个文件，并把 mtime 钉在虚拟时钟的时刻上。"""
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


def collect(watcher, clock, rounds=4, step=2.0):
    """把时钟往前推着 poll 几轮，把这一批事件收齐。"""
    events = []
    for _ in range(rounds):
        clock.advance(step)
        events.extend(watcher.poll())
    return events


class TestWatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.clock = ManualClock(1000.0)
        self.watcher = Watcher(self.root, fs=SysFS(), clock=self.clock)

    def test_first_poll_is_quiet(self):
        self.assertEqual(collect(self.watcher, self.clock), [])

    def test_created_file(self):
        make_file(self.root, "new.txt", b"x", self.clock)
        self.assertEqual(collect(self.watcher, self.clock),
                         [Event("created", "new.txt", False)])

    def test_modified_file(self):
        make_file(self.root, "a.txt", b"aaaa", self.clock)
        self.assertEqual(collect(self.watcher, self.clock),
                         [Event("created", "a.txt", False)])
        self.clock.advance(3.0)
        make_file(self.root, "a.txt", b"bbbb", self.clock)
        self.assertEqual(collect(self.watcher, self.clock),
                         [Event("modified", "a.txt", False)])

    def test_deleted_file(self):
        path = make_file(self.root, "a.txt", b"aaaa", self.clock)
        collect(self.watcher, self.clock)
        self.clock.advance(3.0)
        os.remove(path)
        self.assertEqual(collect(self.watcher, self.clock),
                         [Event("deleted", "a.txt", False)])

    def test_moved_file_is_paired(self):
        path = make_file(self.root, "a.txt", b"aaaa", self.clock)
        collect(self.watcher, self.clock)
        self.clock.advance(3.0)
        os.rename(path, os.path.join(self.root, "b.txt"))
        events = collect(self.watcher, self.clock)
        self.assertIn(Event("moved", "a.txt", False, "b.txt"), events)

    def test_callbacks_get_the_same_events(self):
        seen = []
        self.watcher.subscribe(seen.append)
        make_file(self.root, "n.txt", b"x", self.clock)
        events = collect(self.watcher, self.clock)
        self.assertEqual(seen, events)
        self.assertIs(seen[0], events[0])

    def test_snapshot_follows_poll(self):
        make_file(self.root, "n.txt", b"12345", self.clock)
        collect(self.watcher, self.clock)
        self.assertEqual(self.watcher.snapshot().entry("n.txt").size, 5)
        self.assertIsNotNone(self.watcher.last_poll_at)

    def test_start_and_stop(self):
        self.watcher.start()
        self.watcher.stop()
        self.watcher.stop()


if __name__ == "__main__":
    unittest.main()
