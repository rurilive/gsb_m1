"""修复后的行为钉死：在线调优先级、回滚位置、公平序、容量与同值无副作用。

另带一段 push/弹出/更新/回滚/收尾完全随机混合的序列，逐步跟
SortedListQueue 参考实现对拍。
"""

import random
import unittest

from taskheap import IndexedHeap, SortedListQueue, TaskQueue


class TestUpdatePriority(unittest.TestCase):
    def test_raise_priority_does_not_duplicate(self):
        queue = TaskQueue()
        queue.push("render", 9)
        queue.push("index", 5)
        queue.push("report", 7)
        queue.update_priority("render", 1)
        self.assertEqual(queue.pending(), ["render", "index", "report"])
        self.assertEqual(queue.pop_batch(4), ["render", "index", "report"])
        self.assertEqual(queue.size(), 0)

    def test_lower_priority_moves_back(self):
        queue = TaskQueue()
        queue.push("report", 3)
        queue.push("index", 4)
        queue.update_priority("report", 8)
        self.assertEqual(queue.pending(), ["index", "report"])

    def test_repeated_updates_keep_single_heap_record(self):
        queue = TaskQueue()
        for index in range(30):
            queue.push("t%02d" % index, index % 7)
        for prio in range(20):
            queue.update_priority("t13", prio)
        self.assertEqual(queue.size(), 30)
        self.assertEqual(queue.capacity(), 30)
        served = queue.pop_batch(30)
        self.assertEqual(sorted(served), ["t%02d" % i for i in range(30)])
        self.assertEqual(len(served), len(set(served)))

    def test_same_priority_update_is_a_noop(self):
        queue = TaskQueue()
        for index, task_id in enumerate(("a", "b", "c", "d")):
            queue.push(task_id, 5)
        # 同值更新前后的堆内记录必须是同一条，下标、序号、容量都不动。
        entry_before = queue._queued["b"][1]
        index_before = entry_before.index
        queue.update_priority("b", 5)
        entry_after = queue._queued["b"][1]
        self.assertIs(entry_after, entry_before)
        self.assertEqual(entry_after.index, index_before)
        self.assertEqual(entry_after.seq, entry_before.seq)
        self.assertEqual(queue.capacity(), 4)
        self.assertEqual(queue.pending(), ["a", "b", "c", "d"])

    def test_update_keeps_submission_seq_for_ties(self):
        queue = TaskQueue()
        for task_id in ("a", "b", "c"):
            queue.push(task_id, 5)
        queue.push("late", 5)
        # b 先被调高再调回来，仍然排在 c、late 前面，因为提交序号没变。
        queue.update_priority("b", 1)
        queue.update_priority("b", 5)
        self.assertEqual(queue.pending(), ["a", "b", "c", "late"])

    def test_update_rejects_running_and_unknown_task(self):
        queue = TaskQueue()
        queue.push("a", 1)
        queue.push("b", 2)
        queue.pop()
        with self.assertRaises(KeyError):
            queue.update_priority("a", 9)
        with self.assertRaises(KeyError):
            queue.update_priority("ghost", 9)


class TestRelease(unittest.TestCase):
    def test_release_restores_heap_position(self):
        queue = TaskQueue()
        for task_id, prio in (("a", 1), ("b", 2), ("c", 3), ("d", 4)):
            queue.push(task_id, prio)
        self.assertEqual(queue.pop_batch(2), ["a", "b"])
        queue.release("a")
        self.assertEqual(queue.pending(), ["a", "c", "d"])
        self.assertEqual(queue.pop_batch(3), ["a", "c", "d"])

    def test_release_is_rejected_when_not_running(self):
        queue = TaskQueue()
        queue.push("a", 1)
        with self.assertRaises(KeyError):
            queue.release("a")
        with self.assertRaises(KeyError):
            queue.release("ghost")
        queue.pop()
        queue.done("a")
        with self.assertRaises(KeyError):
            queue.release("a")

    def test_release_keeps_original_seq_and_repops_once(self):
        queue = TaskQueue()
        for task_id in ("a", "b", "c"):
            queue.push(task_id, 4)
        self.assertEqual(queue.pop(), "a")
        queue.release("a")
        self.assertEqual(queue.size(), 3)
        self.assertEqual(queue.pop_batch(3), ["a", "b", "c"])
        self.assertIsNone(queue.pop())


class TestFairness(unittest.TestCase):
    def test_same_priority_is_fifo_across_ops(self):
        queue = TaskQueue()
        for index in range(100):
            queue.push("job-%03d" % index, 7)
        self.assertEqual(queue.pop_batch(10),
                         ["job-%03d" % i for i in range(10)])
        for index in range(100, 120):
            queue.push("job-%03d" % index, 7)
        self.assertEqual(queue.pop_batch(10),
                         ["job-%03d" % i for i in range(10, 20)])
        queue.release("job-003")
        queue.release("job-000")
        # 回滚的两条保留原提交序号，job-000 在 job-003 前面。
        self.assertEqual(queue.pop(), "job-000")
        self.assertEqual(queue.pop(), "job-003")
        self.assertEqual(queue.pop(), "job-020")


class TestHeapCapacity(unittest.TestCase):
    def test_empty_heap_has_no_slots(self):
        heap = IndexedHeap()
        heap.push(1, "a")
        heap.pop_min()
        self.assertEqual((heap.size(), heap.capacity()), (0, 0))

    def test_capacity_stays_same_order_as_size(self):
        heap = IndexedHeap()
        for index in range(1000):
            heap.push(index, "t%04d" % index, index)
        for _ in range(990):
            heap.pop_min()
        self.assertLessEqual(heap.capacity(), max(8, 4 * heap.size()))
        for index in range(1000, 2000):
            heap.push(index, "t%04d" % index, index)
        while heap.pop_min() is not None:
            pass
        self.assertEqual((heap.size(), heap.capacity()), (0, 0))

    def test_restore_sifts_back_into_position(self):
        heap = IndexedHeap()
        for index, prio in enumerate((5, 8, 9, 12)):
            heap.push(prio, "t%d" % index, index)
        top = heap.pop_min()
        self.assertEqual(top.task_id, "t0")
        heap.restore(top)
        self.assertEqual(
            [heap.pop_min().task_id for _ in range(4)],
            ["t0", "t1", "t2", "t3"])

    def test_change_priority_reorders_in_place(self):
        heap = IndexedHeap()
        for index, prio in enumerate((5, 8, 9)):
            heap.push(prio, "t%d" % index, index)
        entry = heap.push(12, "t3", 3)
        heap.change_priority(entry, 1)
        self.assertEqual(heap.peek().task_id, "t3")
        heap.change_priority(entry, 20)
        self.assertEqual(
            [heap.pop_min().task_id for _ in range(4)],
            ["t0", "t1", "t2", "t3"])


class TestQueueCapacity(unittest.TestCase):
    def test_drain_releases_all_slots(self):
        queue = TaskQueue()
        for index in range(500):
            queue.push("job-%04d" % index, index % 13)
        queue.pop_batch(500)
        for task_id in queue.running():
            queue.done(task_id)
        self.assertEqual((queue.size(), queue.capacity()), (0, 0))

    def test_capacity_bounded_after_mixed_traffic(self):
        queue = TaskQueue()
        rnd = random.Random(7)
        counter = 0
        for _ in range(5000):
            roll = rnd.random()
            if roll < 0.5 or queue.size() == 0:
                queue.push("n%05d" % counter, rnd.randrange(50))
                counter += 1
            elif roll < 0.7 and queue.queued("n%05d" % rnd.randrange(counter)):
                task_id = next(iter(queue.pending()))
                queue.update_priority(task_id, rnd.randrange(50))
            else:
                task_id = queue.pop()
                if rnd.random() < 0.5:
                    queue.release(task_id)
                else:
                    queue.done(task_id)
            self.assertLessEqual(queue.capacity(),
                                 max(8, 4 * queue.size() + 8))


class TestRandomParity(unittest.TestCase):
    def _run_fuzz(self, seed, steps, live_limit=40):
        fast, slow = TaskQueue(), SortedListQueue()
        rnd = random.Random(seed)
        counter = 0
        queued_ids = []
        running_ids = []
        finished = []

        def pick(ids):
            return ids[rnd.randrange(len(ids))]

        for step in range(steps):
            roll = rnd.random()
            if roll < 0.40 or not queued_ids:
                task_id = "t%05d" % counter
                counter += 1
                prio = rnd.randrange(1, 8)
                fast.push(task_id, prio)
                slow.push(task_id, prio)
                queued_ids.append(task_id)
            elif roll < 0.60 and queued_ids:
                task_id = pick(queued_ids)
                prio = rnd.randrange(1, 8)
                fast.update_priority(task_id, prio)
                slow.update_priority(task_id, prio)
            elif roll < 0.82 or not running_ids:
                got, want = fast.pop(), slow.pop()
                self.assertEqual(got, want, "seed=%d step=%d" % (seed, step))
                self.assertEqual(fast.pending(), slow.pending(),
                                 "seed=%d step=%d" % (seed, step))
                self.assertEqual(fast.running(), slow.running(),
                                 "seed=%d step=%d" % (seed, step))
                if got is not None:
                    queued_ids.remove(got)
                    running_ids.append(got)
            elif roll < 0.92 and running_ids:
                task_id = pick(running_ids)
                fast.done(task_id)
                slow.done(task_id)
                running_ids.remove(task_id)
                finished.append(task_id)
            elif running_ids:
                task_id = pick(running_ids)
                fast.release(task_id)
                slow.release(task_id)
                running_ids.remove(task_id)
                queued_ids.append(task_id)

            self.assertEqual(fast.size(), slow.size())
            self.assertLessEqual(fast.capacity(),
                                 max(8, 4 * fast.size() + 8))

            # 掺一些非法操作，两边的异常类型必须一致。
            if step % 37 == 0:
                ghost = "ghost-%d" % step
                for method, args in (
                        ("update_priority", (ghost, 1)),
                        ("release", (ghost,)),
                        ("done", (ghost,))):
                    with self.assertRaises(KeyError):
                        getattr(slow, method)(*args)
                    with self.assertRaises(KeyError):
                        getattr(fast, method)(*args)
            if running_ids and step % 53 == 0:
                task_id = pick(running_ids)
                # 执行中的任务不能直接调优先级，也不能重复收尾。
                with self.assertRaises(KeyError):
                    slow.update_priority(task_id, 1)
                with self.assertRaises(KeyError):
                    fast.update_priority(task_id, 1)
                slow.done(task_id)
                fast.done(task_id)
                running_ids.remove(task_id)
                finished.append(task_id)
                with self.assertRaises(KeyError):
                    slow.done(task_id)
                with self.assertRaises(KeyError):
                    fast.done(task_id)
            if queued_ids and step % 71 == 0:
                # 排队中的任务不能直接 done / release。
                task_id = pick(queued_ids)
                for method in ("done", "release"):
                    with self.assertRaises(KeyError):
                        getattr(slow, method)(task_id)
                    with self.assertRaises(KeyError):
                        getattr(fast, method)(task_id)

        # 收尾：执行中的先回滚，再全部弹空并 done，两边逐步一致。
        for task_id in list(running_ids):
            fast.release(task_id)
            slow.release(task_id)
            queued_ids.append(task_id)
        running_ids = []
        while True:
            got, want = fast.pop(), slow.pop()
            self.assertEqual(got, want)
            if got is None:
                break
            fast.done(got)
            slow.done(got)
        self.assertEqual((fast.size(), fast.capacity()), (0, 0))
        self.assertEqual(fast.running(), [])

    def test_fuzz_seeds(self):
        for seed in range(12):
            self._run_fuzz(seed=seed, steps=800)
