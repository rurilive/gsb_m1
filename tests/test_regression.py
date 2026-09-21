"""修复点的边界回归：在线调优先级、回滚归位、同值更新、容量收缩、随机对拍。"""

import random
import unittest

from taskheap import SortedListQueue, TaskQueue


def make_queue(*items):
    queue = TaskQueue()
    for task_id, prio in items:
        queue.push(task_id, prio)
    return queue


class TestUpdatePriority(unittest.TestCase):
    def test_update_removes_stale_entry(self):
        queue = make_queue(("render", 9), ("index", 5), ("report", 7))
        queue.update_priority("render", 1)
        self.assertEqual(queue.pending(), ["render", "index", "report"])
        self.assertEqual(queue.pop_batch(4), ["render", "index", "report"])
        self.assertIsNone(queue.pop())

    def test_update_to_lower_priority_yields(self):
        queue = make_queue(("report", 3), ("index", 4))
        queue.update_priority("report", 8)
        self.assertEqual(queue.pending(), ["index", "report"])
        self.assertEqual(queue.pop_batch(2), ["index", "report"])

    def test_update_keeps_submission_order_within_priority(self):
        queue = make_queue(("first", 1), ("second", 9), ("third", 9))
        queue.update_priority("first", 9)
        self.assertEqual(queue.pop_batch(3), ["first", "second", "third"])

    def test_same_value_update_has_no_side_effects(self):
        queue = make_queue(("a", 3), ("b", 1), ("c", 2))
        before = (queue.pending(), queue.size(), queue.capacity())
        queue.update_priority("b", 1)
        self.assertEqual((queue.pending(), queue.size(), queue.capacity()), before)
        self.assertEqual(queue.pop_batch(3), ["b", "c", "a"])

    def test_update_on_running_task_rejected(self):
        queue = make_queue(("a", 1), ("b", 2))
        queue.pop()
        with self.assertRaises(KeyError):
            queue.update_priority("a", 0)
        queue.done("a")
        with self.assertRaises(KeyError):
            queue.update_priority("a", 0)


class TestRelease(unittest.TestCase):
    def test_release_returns_to_ranked_position(self):
        queue = make_queue(("a", 1), ("b", 2), ("c", 3), ("d", 4))
        self.assertEqual(queue.pop_batch(2), ["a", "b"])
        queue.release("a")
        self.assertEqual(queue.pending(), ["a", "c", "d"])
        self.assertEqual(queue.pop_batch(3), ["a", "c", "d"])

    def test_release_keeps_submission_order(self):
        queue = make_queue(("x", 5), ("y", 5), ("z", 5))
        self.assertEqual(queue.pop_batch(3), ["x", "y", "z"])
        queue.release("y")
        queue.release("x")
        self.assertEqual(queue.pop_batch(2), ["x", "y"])

    def test_release_on_queued_task_rejected(self):
        queue = make_queue(("a", 1))
        with self.assertRaises(KeyError):
            queue.release("a")

    def test_release_after_update_uses_new_priority(self):
        queue = make_queue(("a", 1), ("b", 2), ("c", 3))
        queue.update_priority("c", 0)
        self.assertEqual(queue.pop_batch(2), ["c", "a"])
        queue.release("c")
        self.assertEqual(queue.pending(), ["c", "b"])


class TestCapacity(unittest.TestCase):
    def test_capacity_stays_proportional_under_churn(self):
        queue = TaskQueue()
        for index in range(20000):
            queue.push("job-%05d" % index, index % 97)
            if index % 2 == 0:
                queue.update_priority("job-%05d" % index, 200 + index % 11)
        while queue.size() > 50:
            for task_id in queue.pop_batch(queue.size() - 50):
                queue.done(task_id)
        self.assertLessEqual(queue.capacity(), max(4 * queue.size(), 64))

    def test_capacity_drains_to_zero(self):
        queue = make_queue(*(("t%d" % index, index) for index in range(500)))
        while queue.pop() is not None:
            pass
        self.assertEqual(queue.size(), 0)
        self.assertEqual(queue.capacity(), 0)


class TestAgainstReference(unittest.TestCase):
    def run_mixed_script(self, seed, steps):
        rnd = random.Random(seed)
        fast, slow = TaskQueue(), SortedListQueue()
        live, running = [], []
        for _ in range(steps):
            roll = rnd.random()
            if roll < 0.35 or not live:
                task_id = "t%04d" % rnd.randrange(400)
                if task_id in live or task_id in running:
                    continue
                prio = rnd.randrange(1, 8)
                fast.push(task_id, prio)
                slow.push(task_id, prio)
                live.append(task_id)
            elif roll < 0.55:
                task_id = rnd.choice(live)
                prio = rnd.randrange(1, 8)
                fast.update_priority(task_id, prio)
                slow.update_priority(task_id, prio)
            elif roll < 0.8 or not running:
                got, want = fast.pop(), slow.pop()
                self.assertEqual(got, want)
                if got is None:
                    continue
                live.remove(got)
                running.append(got)
            elif roll < 0.9:
                task_id = running.pop(rnd.randrange(len(running)))
                fast.done(task_id)
                slow.done(task_id)
            else:
                task_id = running.pop(rnd.randrange(len(running)))
                fast.release(task_id)
                slow.release(task_id)
                live.append(task_id)
            self.assertEqual(fast.pending(), slow.pending())
            self.assertEqual(fast.running(), slow.running())
            self.assertEqual(fast.size(), slow.size())
        self.assertEqual(fast.pop_batch(len(live) + 1),
                         slow.pop_batch(len(live) + 1))

    def test_mixed_operations_match_reference(self):
        for seed in (1, 7, 42, 20260921):
            self.run_mixed_script(seed, 600)


if __name__ == "__main__":
    unittest.main()
