"""FileLock 现有行为的锁定测试。"""

import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from xlock import FileLock  # noqa: E402


class FileLockTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="xlock-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "res.lock")
        self.children = []
        self.addCleanup(support.reap, self.children)

    def test_acquire_and_release_roundtrip(self):
        lock = FileLock(self.path, poll=0.02)
        self.assertFalse(lock.is_held())
        self.assertIsNone(lock.owner())
        self.assertTrue(lock.acquire(timeout=0))
        self.assertTrue(lock.is_mine())
        self.assertTrue(lock.is_held())
        self.assertEqual(lock.owner().pid, os.getpid())
        lock.release()
        self.assertFalse(lock.is_mine())
        self.assertFalse(lock.is_held())
        self.assertIsNone(lock.owner())

    def test_acquire_times_out_while_other_process_holds(self):
        holder = support.spawn_holder(self.path, self.children)
        lock = FileLock(self.path, poll=0.02)
        started = time.monotonic()
        self.assertFalse(lock.acquire(timeout=0.4))
        self.assertGreaterEqual(time.monotonic() - started, 0.3)
        self.assertFalse(lock.is_mine())
        self.assertTrue(lock.is_held())
        self.assertEqual(lock.owner().pid, holder.pid)

    def test_lock_is_free_after_holder_releases(self):
        holder = support.spawn_holder(self.path, self.children)
        lock = FileLock(self.path, poll=0.02)
        holder.stdin.write("go\n")
        holder.stdin.flush()
        self.assertTrue(lock.acquire(timeout=5))
        self.assertTrue(lock.is_mine())
        lock.release()
        holder.wait(timeout=5)
        self.assertEqual(holder.returncode, 0)
        self.assertFalse(lock.is_held())

    def test_two_locks_in_one_process_do_not_share(self):
        first = FileLock(self.path, poll=0.02)
        second = FileLock(self.path, poll=0.02)
        self.assertTrue(first.acquire(timeout=0))
        self.assertFalse(second.acquire(timeout=0.3))
        first.release()
        self.assertTrue(second.acquire(timeout=1))
        second.release()
        self.assertFalse(second.is_held())
