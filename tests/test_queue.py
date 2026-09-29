"""FifoQueue 现有行为的锁定测试，本文件一字不许改。"""

import unittest

from taskq.queue import FifoQueue


class TestFifoQueue(unittest.TestCase):
    def test_fresh_queue_is_empty(self):
        q = FifoQueue()
        self.assertEqual(len(q), 0)
        self.assertFalse(bool(q))

    def test_push_returns_task(self):
        q = FifoQueue()
        self.assertEqual(q.push("a"), "a")

    def test_pop_empty_returns_none(self):
        q = FifoQueue()
        self.assertIsNone(q.pop())

    def test_pop_preserves_fifo_order(self):
        q = FifoQueue()
        q.push("a")
        q.push("b")
        q.push("c")
        self.assertEqual([q.pop(), q.pop(), q.pop()], ["a", "b", "c"])

    def test_fifo_is_stable_for_equal_tasks(self):
        q = FifoQueue()
        for i in range(5):
            q.push(i)
        self.assertEqual([q.pop() for _ in range(5)], [0, 1, 2, 3, 4])

    def test_len_tracks_pushes_and_pops(self):
        q = FifoQueue()
        q.push("a")
        q.push("b")
        self.assertEqual(len(q), 2)
        q.pop()
        self.assertEqual(len(q), 1)

    def test_peek_does_not_remove(self):
        q = FifoQueue()
        q.push("a")
        q.push("b")
        self.assertEqual(q.peek(), "a")
        self.assertEqual(len(q), 2)
        self.assertEqual(q.pop(), "a")

    def test_peek_empty_returns_none(self):
        q = FifoQueue()
        self.assertIsNone(q.peek())

    def test_push_none_raises(self):
        q = FifoQueue()
        with self.assertRaises(ValueError):
            q.push(None)

    def test_bool_reflects_emptiness(self):
        q = FifoQueue()
        q.push("a")
        self.assertTrue(bool(q))
        q.pop()
        self.assertFalse(bool(q))

    def test_pop_until_empty_returns_none(self):
        q = FifoQueue()
        q.push("a")
        self.assertEqual(q.pop(), "a")
        self.assertIsNone(q.pop())


if __name__ == "__main__":
    unittest.main()
