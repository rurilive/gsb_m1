"""优雅关闭 close() 的行为测试。

节奏全部用 Event 控制，等待只依赖有限的 wait 超时，
不使用 sleep，任何环境下结果一致。
"""

import threading
import unittest

from workerpool import PoolClosed, WorkerPool
from workerpool.pool import CANCELLED, FINISHED


class TestCloseRejectsNewWork(unittest.TestCase):
    def test_submit_raises_after_close(self):
        pool = WorkerPool(1)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.submit(str, 1)

    def test_map_raises_after_close(self):
        pool = WorkerPool(1)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.map(str, [1, 2])


class TestCloseWithoutTimeout(unittest.TestCase):
    def test_waits_for_all_submitted(self):
        gate = threading.Event()
        started = threading.Event()

        def job():
            started.set()
            gate.wait(5)
            return "ok"

        pool = WorkerPool(1)
        t = pool.submit(job)
        self.assertTrue(started.wait(5))
        outcome = {}

        def closer():
            outcome["report"] = pool.close()

        thread = threading.Thread(target=closer, daemon=True)
        thread.start()
        # gate 未放开，close 必须一直等
        self.assertFalse(thread.join(0.2))
        self.assertTrue(thread.is_alive())
        gate.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        report = outcome["report"]
        self.assertEqual(report.completed, 1)
        self.assertEqual(report.cancelled, [])
        self.assertEqual(t.state, FINISHED)

    def test_completed_counts_only_this_close(self):
        pool = WorkerPool(1)
        t = pool.submit(str, 1)
        self.assertEqual(t.result(5), "1")
        report = pool.close()
        # close 前已落定的不计入 completed
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.cancelled, [])


class TestCloseWithTimeout(unittest.TestCase):
    def test_unsettled_tasks_are_cancelled(self):
        started = threading.Event()
        finish_gate = threading.Event()
        fn_returned = threading.Event()
        queued_ran = threading.Event()

        def slow():
            started.set()
            finish_gate.wait(5)
            fn_returned.set()
            return "slow"

        def queued():
            queued_ran.set()

        pool = WorkerPool(1)
        running = pool.submit(slow)
        waiting = pool.submit(queued)
        self.assertTrue(started.wait(5))

        report = pool.close(grace_timeout=0.2)
        self.assertEqual(report.completed, 0)
        self.assertEqual(set(report.cancelled), {running, waiting})
        self.assertEqual(running.state, CANCELLED)
        self.assertEqual(waiting.state, CANCELLED)
        self.assertTrue(running.done)

        # 在途任务函数跑完后，状态不再翻转
        finish_gate.set()
        self.assertTrue(fn_returned.wait(5))
        # 被取消的排队任务不再执行
        self.assertFalse(queued_ran.wait(0.2))
        self.assertEqual(running.state, CANCELLED)
        self.assertEqual(waiting.state, CANCELLED)

    def test_partial_completion_before_deadline(self):
        quick_gate = threading.Event()
        slow_gate = threading.Event()
        started = [threading.Event(), threading.Event()]

        def job(gate, my_started):
            my_started.set()
            gate.wait(5)
            return "ok"

        pool = WorkerPool(2)
        quick = pool.submit(job, quick_gate, started[0])
        slow = pool.submit(job, slow_gate, started[1])
        self.assertTrue(started[0].wait(5))
        self.assertTrue(started[1].wait(5))

        outcome = {}

        def closer():
            outcome["report"] = pool.close(grace_timeout=0.5)

        thread = threading.Thread(target=closer, daemon=True)
        thread.start()
        quick_gate.set()
        thread.join(5)
        report = outcome["report"]
        self.assertEqual(report.completed, 1)
        self.assertEqual(report.cancelled, [slow])
        self.assertEqual(quick.state, FINISHED)
        self.assertEqual(slow.state, CANCELLED)
        slow_gate.set()


class TestCloseIdempotent(unittest.TestCase):
    def test_second_close_returns_first_report(self):
        pool = WorkerPool(1)
        pool.submit(str, 1)
        first = pool.close()
        second = pool.close(grace_timeout=0.01)
        self.assertIs(second, first)


class TestAtexit(unittest.TestCase):
    def test_registered_by_default(self):
        self.assertTrue(WorkerPool(1).atexit_registered)

    def test_opt_out(self):
        self.assertFalse(WorkerPool(1, atexit=False).atexit_registered)


if __name__ == "__main__":
    unittest.main()
