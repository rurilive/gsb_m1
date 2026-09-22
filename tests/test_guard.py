"""ResourceGuard 现有行为的锁定测试。"""

import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from xlock import LockTimeout, ResourceGuard  # noqa: E402


class GuardTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="xlock-guard-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.guard = ResourceGuard(os.path.join(self.dir, "locks"))
        self.children = []
        self.addCleanup(support.reap, self.children)

    def test_hold_release_and_events(self):
        with self.guard.hold("journal", timeout=0) as lease:
            self.assertEqual(lease.resource, "journal")
            self.assertTrue(self.guard.is_held("journal"))
            self.assertEqual(self.guard.owner("journal").pid, os.getpid())
        self.assertFalse(self.guard.is_held("journal"))
        self.assertEqual([e[1] for e in self.guard.events()], ["enter", "exit"])

    def test_nested_hold_releases_at_outermost(self):
        outer = self.guard.hold("journal", timeout=0)
        inner = self.guard.hold("journal", timeout=0)
        inner.release()
        self.assertTrue(self.guard.is_held("journal"))
        outer.release()
        self.assertFalse(self.guard.is_held("journal"))

    def test_exception_inside_hold_releases(self):
        with self.assertRaises(ZeroDivisionError):
            with self.guard.hold("journal", timeout=0):
                1 / 0
        self.assertFalse(self.guard.is_held("journal"))

    def test_busy_resource_raises_lock_timeout(self):
        holder = support.spawn_holder(self.guard.path("journal"),
                                      self.children)
        started = time.monotonic()
        with self.assertRaises(LockTimeout):
            self.guard.hold("journal", timeout=0.4)
        self.assertGreaterEqual(time.monotonic() - started, 0.3)
        self.assertTrue(self.guard.is_held("journal"))
        self.assertEqual(self.guard.owner("journal").pid, holder.pid)

    def test_lease_release_is_idempotent(self):
        lease = self.guard.hold("journal", timeout=0)
        lease.release()
        lease.release()
        self.assertFalse(self.guard.is_held("journal"))
