"""WorkerPool 现有行为的锁定测试。

线程节奏全部用 Event 控制，等待只依赖有限的 wait 超时，
不使用 sleep，任何环境下结果一致。
"""

import threading
import unittest

from workerpool.pool import FAILED, FINISHED, PENDING, Task, WorkerPool


class TestTask(unittest.TestCase):
    def test_state_machine_success(self):
        t = Task(pow, (2, 8), {})
        self.assertEqual(t.state, PENDING)
        self.assertFalse(t.done)
        t._run()
        self.assertEqual(t.state, FINISHED)
        self.assertTrue(t.done)
        self.assertEqual(t.result(), 256)

    def test_state_machine_failure(self):
        t = Task(int, ("not-a-number",), {})
        t._run()
        self.assertEqual(t.state, FAILED)
        self.assertIsInstance(t.exception(), ValueError)
        with self.assertRaises(ValueError):
            t.result()

    def test_seq_and_repr(self):
        t = Task(pow, (2, 3), {}, seq=5)
        self.assertEqual(t.seq, 5)
        self.assertIn("#5", repr(t))

    def test_fn_attribute(self):
        t = Task(sorted, ([3, 1],), {})
        self.assertIs(t.fn, sorted)


class TestWorkerPool(unittest.TestCase):
    def test_submit_returns_value(self):
        pool = WorkerPool(2)
        t = pool.submit(pow, 2, 10)
        self.assertEqual(t.result(5), 1024)
        self.assertEqual(t.state, FINISHED)

    def test_result_blocks_until_job_completes(self):
        gate = threading.Event()

        def job():
            gate.wait(5)
            return "ok"

        pool = WorkerPool(1)
        t = pool.submit(job)
        # gate 未放开前任务不可能落定
        self.assertFalse(t.wait(0.1))
        gate.set()
        self.assertEqual(t.result(5), "ok")

    def test_exception_does_not_kill_worker(self):
        pool = WorkerPool(1)
        bad = pool.submit(int, "nope")
        self.assertIsInstance(bad.exception(5), ValueError)
        good = pool.submit(str.upper, "ok")
        self.assertEqual(good.result(5), "OK")

    def test_map_returns_in_submission_order(self):
        # 三个任务完成顺序与提交顺序相反，结果仍按提交顺序排列
        pool = WorkerPool(3)
        gates = [threading.Event() for _ in range(3)]
        values = ["a", "b", "c"]

        def job(gate, value):
            gate.wait(5)
            return value

        def releaser():
            for gate in reversed(gates):
                gate.wait(5)
                gate.set()

        threading.Thread(target=releaser, daemon=True).start()
        self.assertEqual(pool.map(job, gates, values), ["a", "b", "c"])

    def test_concurrency_limited_by_size(self):
        pool = WorkerPool(2)
        started = [threading.Event() for _ in range(3)]
        release = threading.Event()

        def job(i):
            started[i].set()
            release.wait(5)
            return i

        tasks = [pool.submit(job, i) for i in range(3)]
        # 两个槽位都能跑起来
        self.assertTrue(started[0].wait(5))
        self.assertTrue(started[1].wait(5))
        # 第三个只能在队列里等，不会并发执行
        self.assertFalse(started[2].wait(0.2))
        release.set()
        self.assertEqual([t.result(5) for t in tasks], [0, 1, 2])

    def test_tasks_snapshot_in_order(self):
        pool = WorkerPool(2)
        tasks = [pool.submit(str, i) for i in range(4)]
        self.assertEqual(pool.tasks, tuple(tasks))
        # 快照是副本，外部追加影响不到池内登记
        snapshot = pool.tasks
        self.assertIsInstance(snapshot, tuple)

    def test_seq_monotonic(self):
        pool = WorkerPool(1)
        t0 = pool.submit(str, 0)
        t1 = pool.submit(str, 1)
        self.assertEqual(t1.seq, t0.seq + 1)

    def test_wait_all_true_when_all_settle(self):
        pool = WorkerPool(2)
        pool.submit(str, 1)
        pool.submit(str, 2)
        self.assertTrue(pool.wait_all(5))

    def test_wait_all_false_on_timeout(self):
        gate = threading.Event()

        def job():
            gate.wait(5)

        pool = WorkerPool(1)
        pool.submit(job)
        self.assertFalse(pool.wait_all(0.1))
        gate.set()
        self.assertTrue(pool.wait_all(5))

    def test_invalid_size(self):
        with self.assertRaises(ValueError):
            WorkerPool(0)

    def test_many_tasks_all_complete(self):
        pool = WorkerPool(4)
        tasks = [pool.submit(lambda x: x * x, i) for i in range(60)]
        self.assertEqual([t.result(10) for t in tasks], [i * i for i in range(60)])


if __name__ == "__main__":
    unittest.main()
