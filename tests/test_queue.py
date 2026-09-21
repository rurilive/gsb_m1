"""TaskQueue 现有行为的锁定测试。"""

import unittest

from taskheap import TaskQueue


def make_queue(*items):
    queue = TaskQueue()
    for task_id, prio in items:
        queue.push(task_id, prio)
    return queue


class TestPushPop(unittest.TestCase):
    def test_pop_on_empty_returns_none(self):
        self.assertIsNone(TaskQueue().pop())
        self.assertEqual(TaskQueue().pop_batch(5), [])

    def test_pop_follows_priority(self):
        queue = make_queue(("build", 5), ("lint", 1), ("e2e", 9), ("unit", 3))
        self.assertEqual(queue.pop_batch(4), ["lint", "unit", "build", "e2e"])
        self.assertIsNone(queue.pop())

    def test_pop_batch_stops_at_count(self):
        queue = make_queue(("a", 1), ("b", 2), ("c", 3))
        self.assertEqual(queue.pop_batch(2), ["a", "b"])
        self.assertEqual(queue.pop_batch(9), ["c"])
        self.assertEqual(queue.pop_batch(1), [])

    def test_same_priority_keeps_submission_order(self):
        queue = make_queue(("job-1", 4), ("job-2", 4), ("job-3", 4))
        self.assertEqual(queue.pop_batch(3), ["job-1", "job-2", "job-3"])


class TestValidation(unittest.TestCase):
    def test_duplicate_push_rejected(self):
        queue = make_queue(("a", 1))
        with self.assertRaises(ValueError):
            queue.push("a", 2)

    def test_prio_must_be_int(self):
        queue = TaskQueue()
        with self.assertRaises(TypeError):
            queue.push("a", 1.5)
        queue.push("b", 1)
        with self.assertRaises(TypeError):
            queue.update_priority("b", None)

    def test_unknown_task_rejected(self):
        queue = make_queue(("a", 1))
        for method, args in (("update_priority", ("ghost", 2)),
                             ("release", ("ghost",)),
                             ("done", ("ghost",))):
            with self.assertRaises(KeyError):
                getattr(queue, method)(*args)

    def test_done_on_queued_task_rejected(self):
        with self.assertRaises(KeyError):
            make_queue(("a", 1)).done("a")


class TestState(unittest.TestCase):
    def test_pop_moves_task_to_running(self):
        queue = make_queue(("a", 1), ("b", 2))
        self.assertEqual(queue.pop(), "a")
        self.assertFalse(queue.queued("a"))
        self.assertTrue(queue.queued("b"))
        self.assertEqual(queue.running(), ["a"])
        self.assertEqual(queue.size(), 1)
        self.assertFalse(TaskQueue().queued("ghost"))
        self.assertEqual(TaskQueue().running(), [])

    def test_done_finishes_task(self):
        queue = make_queue(("a", 1), ("b", 2), ("c", 3))
        queue.pop_batch(2)
        queue.done("a")
        self.assertEqual(queue.running(), ["b"])
        self.assertEqual(queue.size(), 1)
        self.assertGreaterEqual(queue.capacity(), queue.size())


class TestPending(unittest.TestCase):
    def test_pending_follows_pop_order(self):
        queue = make_queue(("slow", 8), ("fast", 1), ("mid", 4))
        self.assertEqual(queue.pending(), ["fast", "mid", "slow"])
        queue.pop()
        self.assertEqual(queue.pending(), ["mid", "slow"])
        self.assertEqual(TaskQueue().pending(), [])
