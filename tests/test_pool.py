"""netpool 语义测试：把 README「语义约定」逐条锁成用例。

并发用例一律用 threading.Event / Barrier 定死节奏，并用 join(timeout)
断言线程确实在预期窗口内结束，不依赖 sleep 碰时序。

红用例（当前源码与 README 不符）集中在 TestReadmeDiscrepancies，
每个红用例上方都注明「README 期望 / 实际发生」。
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from netpool.pool import BorrowTimeout, ConnectionPool, FakeConn, PoolClosedError


JOIN_MARGIN = 10.0  # 线程收尾用的大余量；正常机器上应是毫秒级完成


def wait_until(predicate, timeout=5.0, interval=0.005):
    """轮询到 predicate 为真，超时抛 AssertionError（不裸靠 sleep）。"""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition not met within %.2fs" % timeout)
        time.sleep(interval)


def wait_for_waiters(pool, count, timeout=5.0):
    """等到 pool 内部 Condition 上有 count 个阻塞的 borrow()。"""
    deadline = time.monotonic() + timeout
    with pool._cond:
        while len(pool._cond._waiters) < count:
            if time.monotonic() >= deadline:
                raise AssertionError("expected %d blocked borrowers, got %d"
                                     % (count, len(pool._cond._waiters)))
            pool._cond.wait(0.01)


def start_borrower(pool, timeout):
    """起一个线程阻塞在 borrow(timeout) 上，返回 (thread, result_box, started)。"""
    started = threading.Event()
    result = {}

    def run():
        started.set()
        try:
            result["conn"] = pool.borrow(timeout=timeout)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    started.wait(JOIN_MARGIN)
    return thread, result


class TestBorrowReturn(unittest.TestCase):
    """README 1、2 的基础语义（当前实现应全部满足）。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    def test_idle_connection_is_reused(self):
        # 有空闲连接 → 直接取出，不新建
        conn = self.pool.borrow()
        self.pool.return_conn(conn)
        again = self.pool.borrow()
        self.assertIs(again, conn)
        self.assertEqual(self.pool.stats()["created"], 1)
        self.pool.return_conn(again)

    def test_borrow_marks_inflight(self):
        conn = self.pool.borrow()
        stats = self.pool.stats()
        self.assertEqual(stats["inflight"], 1)
        self.assertEqual(stats["idle"], 0)
        self.pool.return_conn(conn)
        self.assertEqual(self.pool.stats()["inflight"], 0)
        self.assertEqual(self.pool.stats()["idle"], 1)

    def test_creates_new_until_max_size(self):
        # 无空闲且在途数 < max_size → factory 新建
        first = self.pool.borrow()
        second = self.pool.borrow()
        stats = self.pool.stats()
        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["inflight"], 2)
        self.pool.return_conn(first)
        self.pool.return_conn(second)

    def test_borrow_timeout_when_pool_full(self):
        # 池满且无人归还 → 到 deadline 抛 BorrowTimeout
        conns = [self.pool.borrow(), self.pool.borrow()]
        self.assertEqual(self.pool.stats()["inflight"], 2)
        start = time.monotonic()
        with self.assertRaises(BorrowTimeout):
            self.pool.borrow(timeout=0.3)
        elapsed = time.monotonic() - start
        # 留足 CI 余量：至少等过 timeout，且不应提前返回
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertLess(elapsed, 2.0)
        for held in conns:
            self.pool.return_conn(held)

    def test_waiting_borrower_gets_returned_connection_immediately(self):
        # README 1：等待期间只要有连接归还，应立即拿到它
        held = [self.pool.borrow(), self.pool.borrow()]  # 先填满 max_size=2
        thread, result = start_borrower(self.pool, timeout=JOIN_MARGIN)
        wait_for_waiters(self.pool, 1)

        start = time.monotonic()
        self.pool.return_conn(held[0])
        thread.join(JOIN_MARGIN)
        elapsed = time.monotonic() - start

        self.assertFalse(thread.is_alive(), "等待者未在归还后醒来")
        self.assertNotIn("error", result)
        self.assertIs(result["conn"], held[0])
        self.assertLess(elapsed, 2.0, "归还后没有立即拿到连接")
        self.pool.return_conn(result["conn"])
        self.pool.return_conn(held[1])

    def test_return_foreign_connection_raises_value_error(self):
        # README 2：归还非本池借出的连接 → ValueError
        foreign = FakeConn()
        with self.assertRaises(ValueError):
            self.pool.return_conn(foreign)
        # 池内状态不受影响
        self.assertEqual(self.pool.stats()["inflight"], 0)

    def test_double_return_raises_value_error(self):
        # 同一连接归还两次：第二次对池而言就是「非在途连接」→ ValueError
        conn = self.pool.borrow()
        self.pool.return_conn(conn)
        with self.assertRaises(ValueError):
            self.pool.return_conn(conn)
        # 空闲队列里只有一个，没有重复入队
        self.assertEqual(self.pool.stats()["idle"], 1)


class TestUnhealthyReturn(unittest.TestCase):
    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    def test_unhealthy_connection_closed_and_never_requeued(self):
        # ===== 红用例 =====
        # README 期望：return_conn 发现 conn.healthy 为 False 时，立即 close()
        #   并丢弃，绝不回到空闲队列（之后 borrow 应拿到 factory 新建连接）。
        # 实际发生：return_conn 完全不检查 healthy，坏连接原样 append 进空闲
        #   队列；下一个 borrow 直接把这条坏连接又取出去。
        conn = self.pool.borrow()
        conn.healthy = False
        self.pool.return_conn(conn)

        self.assertTrue(conn.closed, "坏连接归还时应被立即 close()")
        stats = self.pool.stats()
        self.assertEqual(stats["idle"], 0, "坏连接绝不能回到空闲队列")

        reused = self.pool.borrow()
        self.assertIsNot(reused, conn, "不应再次借出已判死的连接")
        self.pool.return_conn(reused)


class TestClose(unittest.TestCase):
    """README 3 的基础语义（幂等 / 关空闲 / 在途归还丢弃）。"""

    def test_close_is_idempotent_and_closes_idle(self):
        pool = ConnectionPool(max_size=4)
        held = pool.borrow()
        idle_one = pool.borrow()
        pool.return_conn(idle_one)

        pool.close()
        pool.close()  # 幂等：重复调用不报错
        self.assertTrue(idle_one.closed)
        self.assertFalse(held.closed)  # close 只关空闲，不关在途

        # 在途连接随后归还：直接 close 丢弃，不进池
        pool.return_conn(held)
        self.assertTrue(held.closed)
        self.assertEqual(pool.stats()["idle"], 0)
        self.assertEqual(pool.stats()["inflight"], 0)

    def test_borrow_after_close_raises_pool_closed(self):
        pool = ConnectionPool(max_size=2)
        pool.close()
        with self.assertRaises(PoolClosedError):
            pool.borrow(timeout=0.1)

    def test_return_foreign_after_close_still_value_error(self):
        # close 不应吞掉「非本池连接」的 ValueError
        pool = ConnectionPool(max_size=2)
        pool.close()
        with self.assertRaises(ValueError):
            pool.return_conn(FakeConn())


class TestReadmeDiscrepancies(unittest.TestCase):
    """当前源码与 README 有出入、预期失败的用例。"""

    def test_waiting_borrower_woken_on_every_return(self):
        # ===== 红用例 =====
        # README 期望：池满时两个等待者排队；一次归还只够一个等待者拿，
        #   拿到连接的等待者返回，没抢到的等待者继续等待（不超时、不报错）。
        # 实际发生：return_conn 用 notify_all() 唤醒全部等待者，而 borrow
        #   醒来后只 wait 一次、抢不到空闲连接就直接抛 BorrowTimeout——
        #   即便距离 deadline 还有很久，且之后确实还会有连接归还。
        pool = ConnectionPool(max_size=1, borrow_timeout=1.0)
        held = pool.borrow()
        r1 = {}
        r2 = {}
        try:
            t1, r1 = start_borrower(pool, timeout=JOIN_MARGIN)
            t2, r2 = start_borrower(pool, timeout=JOIN_MARGIN)
            wait_for_waiters(pool, 2)

            pool.return_conn(held)  # 只够一个等待者拿
            t1.join(JOIN_MARGIN)
            t2.join(JOIN_MARGIN)
            self.assertFalse(t1.is_alive() or t2.is_alive(),
                             "等待者线程未能结束")

            winners = [r for r in (r1, r2) if "conn" in r]
            self.assertEqual(len(winners), 1, "应有且仅有一个等待者拿到连接")

            for i, result in enumerate((r1, r2)):
                self.assertNotIsInstance(
                    result.get("error"), BorrowTimeout,
                    "等待者 %d 未抢到连接也应继续等到归还，而不是立刻超时" % i)
        finally:
            pool.close()
            for result in (r1, r2):
                if "conn" in result:
                    pool.return_conn(result["conn"])

    def test_close_immediately_wakes_waiting_borrowers(self):
        # ===== 红用例 =====
        # README 期望：close() 后正在 borrow 中等待的调用方必须立即收到
        #   PoolClosedError，不允许等到超时。
        # 实际发生：close() 只置 _closed 标志、关闭空闲连接，没有
        #   notify_all()；等待者在 Condition 上一直睡到自己的 timeout
        #   （本例 10s）才醒来发现池已关闭。
        pool = ConnectionPool(max_size=1, borrow_timeout=1.0)
        held = pool.borrow()
        thread, result = start_borrower(pool, timeout=JOIN_MARGIN)
        wait_for_waiters(pool, 1)

        start = time.monotonic()
        pool.close()
        thread.join(2.0)
        elapsed = time.monotonic() - start

        self.assertFalse(
            thread.is_alive(),
            "close() 后等待者仍在阻塞（实际会睡到 timeout=%.0fs）" % JOIN_MARGIN)
        self.assertIsInstance(result.get("error"), PoolClosedError)
        self.assertLess(elapsed, 2.0, "等待者没有在 close 后立即收到异常")

        thread.join(JOIN_MARGIN)
        pool.return_conn(held)  # 池已关闭：在途连接归还即丢弃


class TestConcurrency(unittest.TestCase):
    """真实并发用例：threading + Barrier/Event 同步，节奏完全确定。"""

    def test_created_never_exceeds_max_size_under_burst(self):
        # README 4：8 线程同时冲击 max_size=2 的池，created 总数不得超过 2
        pool = ConnectionPool(max_size=2, borrow_timeout=5.0)
        threads_n = 8
        barrier = threading.Barrier(threads_n)
        release = threading.Event()
        held = []
        held_lock = threading.Lock()

        def worker():
            barrier.wait()  # 所有线程同时发起 borrow，制造真竞争
            try:
                conn = pool.borrow(timeout=5.0)
            except BorrowTimeout:
                return
            with held_lock:
                held.append(conn)
            release.wait(JOIN_MARGIN)
            pool.return_conn(conn)

        threads = [threading.Thread(target=worker) for _ in range(threads_n)]
        for thread in threads:
            thread.start()

        # 等系统稳定到：2 个在途 + 6 个阻塞等待者
        wait_until(lambda: pool.stats()["inflight"] == 2)
        wait_for_waiters(pool, threads_n - 2)

        stats = pool.stats()
        self.assertEqual(stats["created"], 2)
        self.assertLessEqual(stats["created"], pool.max_size)

        release.set()
        for thread in threads:
            thread.join(JOIN_MARGIN)
            self.assertFalse(thread.is_alive())

        stats = pool.stats()
        self.assertEqual(stats["inflight"], 0)
        self.assertEqual(stats["idle"], 2)
        self.assertLessEqual(stats["created"], pool.max_size)
        pool.close()

    def test_concurrent_borrow_return_churn(self):
        # 高并发反复借还：全部健康连接，不应有任何异常，created 全程不超过
        # max_size，结束后在途清零
        pool = ConnectionPool(max_size=3, borrow_timeout=5.0)
        threads_n = 8
        rounds = 100
        errors = []
        start_gate = threading.Event()

        def worker():
            start_gate.wait(JOIN_MARGIN)
            for _ in range(rounds):
                try:
                    conn = pool.borrow(timeout=5.0)
                    pool.return_conn(conn)
                except Exception as exc:
                    errors.append(exc)
                    return

        threads = [threading.Thread(target=worker) for _ in range(threads_n)]
        for thread in threads:
            thread.start()
        start_gate.set()  # 同时开跑，大量线程会真的阻塞在池满等待路径上
        for thread in threads:
            thread.join(JOIN_MARGIN)
            self.assertFalse(thread.is_alive())

        self.assertEqual(errors, [])
        stats = pool.stats()
        self.assertEqual(stats["inflight"], 0)
        self.assertLessEqual(stats["idle"], pool.max_size)
        self.assertLessEqual(stats["created"], pool.max_size)
        pool.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
