"""Pool 提交、取结果、取消与统计的基线。"""

import threading
import time
import unittest

from stealpool.errors import PoolClosed, TaskCancelled
from stealpool.pool import Pool
from stealpool.reference import TreeRunner, random_tree, run_sequential


class SubmitTest(unittest.TestCase):
    def test_result_round_trip(self):
        with Pool(2) as pool:
            futures = [pool.submit(pow, i, 2) for i in range(8)]
            self.assertEqual([f.result() for f in futures], [i * i for i in range(8)])
            self.assertEqual(pool.submit(sorted, [3, 1, 2], reverse=True).result(), [3, 2, 1])

    def test_exception_propagates(self):
        with Pool(2) as pool:
            def boom():
                raise ValueError("炸了")
            future = pool.submit(boom)
            with self.assertRaises(ValueError):
                future.result()
            self.assertTrue(future.done())
            self.assertFalse(future.cancelled())

    def test_shutdown_waits_for_queued_tasks(self):
        pool = Pool(2)
        flags = []
        futures = [pool.submit(flags.append, i) for i in range(6)]
        pool.shutdown(wait=True)
        self.assertEqual(sorted(flags), list(range(6)))
        for thread in pool._threads:
            self.assertFalse(thread.is_alive())
        for future in futures:
            self.assertEqual(future.state(), "finished")

    def test_bad_construction_and_submit_after_close(self):
        with self.assertRaises(ValueError):
            Pool(0)
        pool = Pool(1)
        pool.shutdown()
        with self.assertRaises(PoolClosed):
            pool.submit(sum, [1])


class CancelTest(unittest.TestCase):
    def test_cancel_queued_task_skips_execution(self):
        pool = Pool(1)
        release = threading.Event()
        blocker = pool.submit(release.wait, 5.0)
        victim = pool.submit(sum, [1, 2, 3])
        self.assertTrue(victim.cancel())
        self.assertTrue(victim.cancelled())
        with self.assertRaises(TaskCancelled):
            victim.result()
        release.set()
        self.assertTrue(blocker.result(5.0))
        pool.shutdown()


class NestedSubmitTest(unittest.TestCase):
    def test_task_can_submit_and_wait_for_child(self):
        with Pool(2) as pool:
            def parent():
                child = pool.submit(sum, [1, 2, 3])
                return child.result() * 10
            self.assertEqual(pool.submit(parent).result(), 60)


class StatsTest(unittest.TestCase):
    def test_counters_after_run(self):
        pool = Pool(2)
        futures = [pool.submit(sum, [i]) for i in range(4)]
        futures.append(pool.submit(lambda: 1 / 0))
        for future in futures[:-1]:
            future.result()
        with self.assertRaises(ZeroDivisionError):
            futures[-1].result()
        time.sleep(0.02)  # 让 worker 有空把最后的累计刷进来
        pool.shutdown()
        snap = pool.stats()
        self.assertEqual(snap["workers"], 2)
        self.assertEqual((snap["submitted"], snap["completed"], snap["failed"]), (5, 4, 1))
        self.assertGreaterEqual(snap["steals"], 0)
        self.assertEqual((len(snap["busy_seconds"]), len(snap["idle_seconds"])), (2, 2))
        self.assertEqual(sum(snap["tasks"]), 5)
        self.assertGreater(sum(snap["idle_seconds"]), 0.0)


class TreeCrossCheckTest(unittest.TestCase):
    def test_parallel_tree_matches_sequential(self):
        tree = random_tree(11, depth=2, fanout=2)
        expected = run_sequential(tree, sleep=lambda seconds: None)
        with Pool(8) as pool:
            got = TreeRunner(pool, sleep=lambda seconds: None).run(tree)
        self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
