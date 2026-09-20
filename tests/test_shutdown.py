"""优雅关闭 close(grace_timeout) 的行为测试。

线程节奏全部用 Event 控制，等待只依赖有限的 wait 超时，
不使用 sleep，任何环境下结果一致。
"""

import os
import subprocess
import sys
import threading
import time
import unittest
from concurrent.futures import CancelledError

from workerpool import PoolClosed, WorkerPool
from workerpool.pool import (
    CANCELLED,
    FINISHED,
    PENDING,
    RUNNING,
)


class TestCloseRejectsNewWork(unittest.TestCase):
    def test_submit_raises_pool_closed_after_close(self):
        pool = WorkerPool(2, atexit=False)
        pool.submit(str, 1).result(5)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.submit(str, 2)

    def test_map_raises_pool_closed_after_close(self):
        pool = WorkerPool(2, atexit=False)
        pool.close()
        with self.assertRaises(PoolClosed):
            pool.map(str, range(3))

    def test_pool_closed_is_runtime_error(self):
        self.assertTrue(issubclass(PoolClosed, RuntimeError))


class TestGracefulShutdown(unittest.TestCase):
    def test_no_timeout_waits_for_all_settled(self):
        pool = WorkerPool(2, atexit=False)
        gates = [threading.Event() for _ in range(3)]
        started = [threading.Event() for _ in range(2)]

        def job(i):
            if i < 2:
                started[i].set()
            gates[i].wait(5)
            return i

        tasks = [pool.submit(job, i) for i in range(3)]

        def do_close():
            pool.close()  # 无时限，必须等到任务落定

        closer = threading.Thread(target=do_close)
        closer.start()
        self.assertTrue(started[0].wait(5))
        self.assertTrue(started[1].wait(5))
        self.assertTrue(closer.is_alive())  # 任务没放闸前 close 不能返回
        for gate in gates:
            gate.set()
        closer.join(5)
        self.assertFalse(closer.is_alive())
        self.assertEqual([t.state for t in tasks], [FINISHED] * 3)

    def test_timeout_cancels_running_and_queued(self):
        pool = WorkerPool(1, atexit=False)
        started = threading.Event()
        release = threading.Event()

        def slow():
            started.set()
            release.wait(5)

        running = pool.submit(slow)
        queued = pool.submit(slow)
        self.assertTrue(started.wait(5))

        report = pool.close(grace_timeout=0.1)
        self.assertEqual(running.state, CANCELLED)
        self.assertEqual(queued.state, CANCELLED)
        self.assertTrue(running.done)
        self.assertTrue(queued.done)
        self.assertEqual(report["completed"], 0)
        self.assertEqual(report["cancelled"], [running, queued])

        # 排队的任务函数从未执行；放闸后在跑的任务函数跑完也不翻状态
        release.set()
        running.wait(5)
        self.assertEqual(running.state, CANCELLED)
        self.assertEqual(queued.state, CANCELLED)

    def test_queued_task_function_never_runs_after_cancel(self):
        pool = WorkerPool(1, atexit=False)
        release_first = threading.Event()
        first_started = threading.Event()
        queued_started = threading.Event()

        def first():
            first_started.set()
            release_first.wait(5)

        def queued():
            queued_started.set()

        pool.submit(first)
        t2 = pool.submit(queued)
        self.assertTrue(first_started.wait(5))
        pool.close(grace_timeout=0.1)
        self.assertEqual(t2.state, CANCELLED)
        release_first.set()
        # 给工作线程足够时间尝试出队（若实现错误它会执行 queued）
        self.assertFalse(queued_started.wait(0.3))

    def test_completed_count_only_covers_this_close(self):
        pool = WorkerPool(2, atexit=False)
        # 关闭前已落定的不计入 completed
        done_before = pool.submit(str, 1)
        self.assertTrue(done_before.wait(5))

        # 关闭期间落定的才计入；这次给足宽限全部完成
        during = [pool.submit(str, i) for i in range(4)]
        report = pool.close(grace_timeout=5)
        self.assertTrue(all(t.state == FINISHED for t in during))
        self.assertEqual(report["completed"], 4)
        self.assertEqual(report["cancelled"], [])

    def test_close_mixes_completed_and_cancelled(self):
        pool = WorkerPool(1, atexit=False)
        release_first = threading.Event()
        release_rest = threading.Event()  # 永不放开
        first_started = threading.Event()
        second_started = threading.Event()

        def first_job():
            first_started.set()
            release_first.wait(5)
            return 0

        def slow(start_event):
            start_event.set()
            release_rest.wait(5)

        # size=1：第一个在跑，后两个排队；关闭中途放开，第一个完成、其余取消
        first = pool.submit(first_job)
        second = pool.submit(slow, second_started)
        third = pool.submit(slow, threading.Event())
        self.assertTrue(first_started.wait(5))

        # 只放开在跑的第一个：它在宽限期内落定，后面的等不到放闸
        release_first.set()
        report = pool.close(grace_timeout=0.5)
        self.assertEqual(first.state, FINISHED)
        self.assertTrue(second_started.wait(5))  # 第二个已升为在跑
        self.assertEqual(second.state, CANCELLED)
        self.assertEqual(third.state, CANCELLED)
        self.assertEqual(report["completed"], 1)
        self.assertEqual(report["cancelled"], [second, third])

    def test_report_attribute_access(self):
        pool = WorkerPool(1, atexit=False)
        started = threading.Event()
        release = threading.Event()

        def slow():
            started.set()
            release.wait(5)

        pool.submit(slow)
        self.assertTrue(started.wait(5))
        report = pool.close(grace_timeout=0.1)
        release.set()
        self.assertEqual(report.completed, 0)
        self.assertEqual(len(report.cancelled), 1)


class TestCancelledHandle(unittest.TestCase):
    def test_result_and_exception_raise_cancelled_error(self):
        pool = WorkerPool(1, atexit=False)
        release = threading.Event()
        started = threading.Event()

        def slow():
            started.set()
            release.wait(5)

        task = pool.submit(slow)
        self.assertTrue(started.wait(5))
        pool.close(grace_timeout=0.1)
        release.set()
        with self.assertRaises(CancelledError):
            task.result(5)
        with self.assertRaises(CancelledError):
            task.exception(5)


class TestCloseIdempotent(unittest.TestCase):
    def test_repeated_close_returns_first_report(self):
        pool = WorkerPool(1, atexit=False)
        release = threading.Event()
        started = threading.Event()

        def slow():
            started.set()
            release.wait(5)

        task = pool.submit(slow)
        self.assertTrue(started.wait(5))
        first = pool.close(grace_timeout=0.1)
        release.set()
        second = pool.close(grace_timeout=5)
        third = pool.close()
        self.assertIs(first, second)
        self.assertIs(first, third)
        self.assertEqual(second["cancelled"], [task])

    def test_close_empty_pool(self):
        pool = WorkerPool(2, atexit=False)
        report = pool.close()
        self.assertEqual(report["completed"], 0)
        self.assertEqual(report["cancelled"], [])

    def test_concurrent_close_callers_share_first_report(self):
        pool = WorkerPool(1, atexit=False)
        release = threading.Event()
        started = threading.Event()

        def slow():
            started.set()
            release.wait(5)

        task = pool.submit(slow)
        self.assertTrue(started.wait(5))

        reports = []

        def closer():
            reports.append(pool.close(grace_timeout=0.5))

        callers = [threading.Thread(target=closer) for _ in range(3)]
        for t in callers:
            t.start()
        release.set()
        for t in callers:
            t.join(5)
            self.assertFalse(t.is_alive())
        self.assertEqual(len(reports), 3)
        self.assertIs(reports[0], reports[1])
        self.assertIs(reports[1], reports[2])
        self.assertEqual(reports[0]["completed"], 1)
        self.assertEqual(task.state, FINISHED)


class TestAtexit(unittest.TestCase):
    def test_atexit_registered_flag(self):
        registered = WorkerPool(1, atexit=True)
        try:
            self.assertTrue(registered.atexit_registered)
        finally:
            registered.close()

        not_registered = WorkerPool(1, atexit=False)
        try:
            self.assertFalse(not_registered.atexit_registered)
        finally:
            not_registered.close()

    def test_atexit_finishes_inflight_tasks_on_exit(self):
        # 子进程里：任务等一个临时文件出现；atexit 钩子必须无时限等到它落定。
        marker = os.path.join(os.path.dirname(__file__), "_atexit_marker.tmp")
        if os.path.exists(marker):
            os.remove(marker)
        code = (
            "import sys\n"
            "from workerpool import WorkerPool\n"
            f"marker = {marker!r}\n"
            "def job():\n"
            "    import time\n"
            "    for _ in range(200):\n"
            "        if __import__('os').path.exists(marker):\n"
            "            return 'done'\n"
            "        time.sleep(0.02)\n"
            "    return 'timeout'\n"
            "pool = WorkerPool(1)\n"
            "t = pool.submit(job)\n"
            "open(marker + '.started', 'w').close()\n"
            "sys.exit(0)\n"
        )
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        started_marker = marker + ".started"
        try:
            for _ in range(250):
                if os.path.exists(started_marker):
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.02)
            self.assertTrue(os.path.exists(started_marker))
            # 子进程此时应阻塞在 atexit 收尾上
            self.assertIsNone(proc.poll())
            with open(marker, "w"):
                pass
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, stderr.decode())
        finally:
            for path in (marker, started_marker):
                if os.path.exists(path):
                    os.remove(path)


if __name__ == "__main__":
    unittest.main()
