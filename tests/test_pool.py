"""netpool 连接池语义测试（标准库 unittest）。

唯一准绳是 README.md 的「语义约定」一节。与源码不符的红用例，在测试方法
上方注释标明「README 期望 / 实际行为」。

运行（仓库根目录下）：
    python3 -m unittest discover -s tests -v
    python3 tests/test_pool.py
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from netpool.pool import (  # noqa: E402
    BorrowTimeout,
    ConnectionPool,
    FakeConn,
    PoolClosedError,
)


class _PoolTestBase(unittest.TestCase):
    def make_pool(self, **kwargs):
        pool = ConnectionPool(**kwargs)
        self.addCleanup(pool.close)
        return pool

    def join_all(self, threads, timeout=5.0):
        for t in threads:
            t.join(timeout)
        for t in threads:
            self.assertFalse(t.is_alive(), "线程未在 %.1fs 内结束" % timeout)


class SingleThreadSemanticsTest(_PoolTestBase):
    def test_borrow_creates_conn_when_pool_not_full(self):
        # README 1: 无空闲但池未满（在途数 < max_size）→ 用 factory 新建一个。
        pool = self.make_pool(max_size=2)
        conn = pool.borrow()
        self.assertIsInstance(conn, FakeConn)
        self.assertEqual(
            pool.stats(),
            {"idle": 0, "inflight": 1, "created": 1, "closed": False},
        )

    def test_borrow_reuses_idle_conn(self):
        # README 1: 有空闲连接 → 直接取出并标记为在途（不新建）。
        pool = self.make_pool(max_size=2)
        conn = pool.borrow()
        pool.return_conn(conn)
        self.assertEqual(pool.stats()["idle"], 1)
        again = pool.borrow()
        self.assertIs(again, conn)
        stats = pool.stats()
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["idle"], 0)
        self.assertEqual(stats["inflight"], 1)

    def test_borrow_timeout_when_full_and_nobody_returns(self):
        # README 1: 池满 → 等待归还；到 deadline 仍没有 → 抛 BorrowTimeout。
        pool = self.make_pool(max_size=1)
        pool.borrow()
        t0 = time.monotonic()
        with self.assertRaises(BorrowTimeout):
            pool.borrow(timeout=0.3)
        elapsed = time.monotonic() - t0
        self.assertGreaterEqual(elapsed, 0.25, "不应早于 deadline 抛超时")
        self.assertLess(elapsed, 1.5, "到点应抛 BorrowTimeout，不应久挂")

    def test_borrow_after_close_raises(self):
        # README 1: 池已关闭 → 抛 PoolClosedError。
        pool = self.make_pool(max_size=1)
        pool.close()
        with self.assertRaises(PoolClosedError):
            pool.borrow()

    def test_unhealthy_returned_conn_is_closed_and_discarded(self):
        # README 期望: 「conn.healthy 为 False 的连接：归还时应立即 close()
        #              并丢弃，绝不回到空闲队列」。
        # 实际行为:   return_conn 完全不检查 healthy，判死的连接原样进入空闲
        #              队列（conn.closed 仍为 False，idle +1），下次 borrow
        #              还会把这个已判死的连接再发出去。
        pool = self.make_pool(max_size=2)
        conn = pool.borrow()
        conn.healthy = False
        pool.return_conn(conn)
        self.assertTrue(conn.closed, "坏连接归还后应立即 close()")
        self.assertEqual(pool.stats()["idle"], 0, "坏连接不应回到空闲队列")

    def test_return_foreign_conn_raises(self):
        # README 2: 归还非本池借出的连接 → ValueError。
        pool = self.make_pool(max_size=1)
        with self.assertRaises(ValueError):
            pool.return_conn(FakeConn())
        conn = pool.borrow()
        pool.return_conn(conn)
        with self.assertRaises(ValueError):
            pool.return_conn(conn)  # 已归还的连接不在在途集合里，再还即非法

    def test_close_is_idempotent_and_closes_idle_conns(self):
        # README 3: close() 幂等；关闭所有空闲连接。
        pool = self.make_pool(max_size=2)
        conns = [pool.borrow() for _ in range(2)]
        for c in conns:
            pool.return_conn(c)
        pool.close()
        pool.close()  # 幂等，不应抛异常
        for c in conns:
            self.assertTrue(c.closed)
        stats = pool.stats()
        self.assertEqual(stats["idle"], 0)
        self.assertTrue(stats["closed"])

    def test_inflight_conn_returned_after_close_is_closed(self):
        # README 3: 在途连接随后归还时：直接 close() 丢弃，不进池。
        pool = self.make_pool(max_size=1)
        conn = pool.borrow()
        pool.close()
        pool.return_conn(conn)  # 不应抛异常
        self.assertTrue(conn.closed)
        self.assertEqual(pool.stats()["idle"], 0)


class ConcurrencyTest(_PoolTestBase):
    def test_return_hands_conn_to_waiting_borrower(self):
        # README 1: 池满 → 等待归还；等待期间只要有连接归还，应立即拿到它。
        pool = self.make_pool(max_size=1)
        conn0 = pool.borrow()
        started = threading.Event()
        outcome = {}

        def waiter():
            started.set()
            t0 = time.monotonic()
            outcome["conn"] = pool.borrow(timeout=2.0)
            outcome["elapsed"] = time.monotonic() - t0

        t = threading.Thread(target=waiter)
        t.start()
        self.assertTrue(started.wait(2.0))
        time.sleep(0.2)  # 留余量，确保等待者已进入 cond.wait
        pool.return_conn(conn0)
        self.join_all([t])
        self.assertIs(outcome["conn"], conn0, "归还的连接应立即交给等待者")
        self.assertLess(outcome["elapsed"], 1.5, "不应等到快超时才拿到")
        pool.return_conn(outcome["conn"])

    def test_close_wakes_waiting_borrower_immediately(self):
        # README 期望: close() 时「正在 borrow 中等待的调用方必须立即收到
        #              PoolClosedError，不允许等到超时」。
        # 实际行为:   close() 只置 _closed 标志，从不 notify；等待者要睡满
        #              整个 timeout 被 wait 超时唤醒后才抛 PoolClosedError。
        pool = self.make_pool(max_size=1)
        pool.borrow()  # 占满池，让下面的 borrow 进入等待
        started = threading.Event()
        outcome = {}

        def waiter():
            started.set()
            t0 = time.monotonic()
            try:
                pool.borrow(timeout=2.0)
                outcome["error"] = None
            except Exception as e:  # noqa: BLE001
                outcome["error"] = e
            outcome["elapsed"] = time.monotonic() - t0

        t = threading.Thread(target=waiter)
        t.start()
        self.assertTrue(started.wait(2.0))
        time.sleep(0.3)  # 留余量，确保等待者已进入 cond.wait
        pool.close()
        self.join_all([t])
        self.assertIsInstance(outcome["error"], PoolClosedError)
        self.assertLess(
            outcome["elapsed"],
            1.0,
            "close 后等待者应立刻收到 PoolClosedError，实际耗时 %.2fs"
            % outcome["elapsed"],
        )

    def test_full_pool_multiple_waiters_no_premature_timeout(self):
        # README 期望: 池满等待期间「只要有连接归还，应立即拿到它」，只有
        #              「到 deadline 仍没有」才抛 BorrowTimeout —— 多个等待者
        #              中没抢到连接的那个应继续等待，直到拿到或到 deadline。
        # 实际行为:   return_conn 的 notify_all 唤醒所有等待者后，没抢到连接
        #              的等待者不会回到等待，而是远早于 deadline 立刻抛
        #              BorrowTimeout。
        pool = self.make_pool(max_size=1)
        conn0 = pool.borrow()
        ready = [threading.Event(), threading.Event()]
        results = [None, None]

        def waiter(i):
            ready[i].set()
            try:
                conn = pool.borrow(timeout=2.0)
                results[i] = conn
                time.sleep(0.1)  # 模拟使用后归还，另一个等待者理应能拿到
                pool.return_conn(conn)
            except Exception as e:  # noqa: BLE001
                results[i] = e

        threads = [threading.Thread(target=waiter, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for e in ready:
            self.assertTrue(e.wait(2.0))
        time.sleep(0.5)  # 留余量，确保两个等待者都已阻塞在 cond.wait
        pool.return_conn(conn0)
        self.join_all(threads)
        errors = [r for r in results if isinstance(r, Exception)]
        self.assertEqual(
            [],
            ["%r" % e for e in errors],
            "两个等待者都应在 timeout 内拿到连接（连接会被轮流归还）",
        )

    def test_created_capped_at_max_size_under_concurrent_churn(self):
        # README 4: 连接创建总数不超过 max_size（stats()["created"] <= max_size）。
        pool = self.make_pool(max_size=4, borrow_timeout=2.0)
        gate = threading.Event()
        errors = []

        def worker():
            gate.wait(2.0)
            try:
                for _ in range(50):
                    conn = pool.borrow()
                    pool.return_conn(conn)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        gate.set()  # 统一放行，制造真实并发
        self.join_all(threads, timeout=15.0)
        self.assertEqual([], ["%r" % e for e in errors])
        self.assertLessEqual(pool.stats()["created"], pool.max_size)


if __name__ == "__main__":
    unittest.main()
