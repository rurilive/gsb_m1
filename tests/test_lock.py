"""LocalLock 现有行为的锁定测试。"""

import threading
import unittest

from mutexly import LocalLock


class TestLocalLock(unittest.TestCase):
    def test_fresh_lock_is_free(self):
        lock = LocalLock()
        self.assertIsNone(lock.holder())
        self.assertFalse(lock.is_locked())

    def test_acquire_then_holder(self):
        lock = LocalLock()
        self.assertTrue(lock.acquire("t1"))
        self.assertEqual(lock.holder(), "t1")
        self.assertTrue(lock.is_locked())

    def test_acquire_blocked_by_other_owner(self):
        lock = LocalLock()
        lock.acquire("t1")
        self.assertFalse(lock.acquire("t2"))
        self.assertEqual(lock.holder(), "t1")

    def test_reacquire_by_same_owner_fails(self):
        lock = LocalLock()
        lock.acquire("t1")
        self.assertFalse(lock.acquire("t1"))
        self.assertEqual(lock.holder(), "t1")

    def test_release_by_holder(self):
        lock = LocalLock()
        lock.acquire("t1")
        self.assertTrue(lock.release("t1"))
        self.assertIsNone(lock.holder())
        self.assertFalse(lock.is_locked())

    def test_release_by_other_owner_fails(self):
        lock = LocalLock()
        lock.acquire("t1")
        self.assertFalse(lock.release("t2"))
        self.assertEqual(lock.holder(), "t1")

    def test_release_free_lock_fails(self):
        lock = LocalLock()
        self.assertFalse(lock.release("t1"))

    def test_release_twice_second_fails(self):
        lock = LocalLock()
        lock.acquire("t1")
        self.assertTrue(lock.release("t1"))
        self.assertFalse(lock.release("t1"))

    def test_acquire_after_release_succeeds(self):
        lock = LocalLock()
        lock.acquire("t1")
        lock.release("t1")
        self.assertTrue(lock.acquire("t2"))
        self.assertEqual(lock.holder(), "t2")

    def test_concurrent_acquire_single_winner(self):
        lock = LocalLock()
        winners = []
        guard = threading.Lock()
        threads = []

        def worker(name):
            if lock.acquire(name):
                with guard:
                    winners.append(name)

        for t in range(8):
            th = threading.Thread(target=worker, args=(f"t{t}",))
            threads.append(th)
        for th in threads:
            th.start()
        for th in threads:
            th.join(5)
        self.assertEqual(len(winners), 1)


if __name__ == "__main__":
    unittest.main()
