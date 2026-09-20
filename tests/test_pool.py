"""netpool 语义测试。

以 README「语义约定」为准逐条锁定。所有多线程用例使用 threading.Event /
Barrier 把调度节奏定死，不依赖 sleep 碰运气；断言超时一律留足余量。

test_red_* 为当前源码与 README 不符而失败的用例，每个用例上方注释写明
「README 期望 / 实际行为」。README 未约定的自由行为不设为红用例。
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

# 断言 deadline：给线程调度留足余量，但一旦死锁仍能快速失败。
WAIT = 5.0
# “立即唤醒”的判定窗口：真正的 Condition 唤醒是毫秒级，1 秒余量充足，
# 又能让红用例快速失败而不必等完等待者的长 timeout。
IMMEDIATE = 1.0


def wait_for(event, timeout=WAIT):
    """事件必须在 timeout 内被 set，否则当前用例失败。"""
    if not event.wait(timeout):
        raise AssertionError("thread did not reach expected state within %.1fs" % timeout)


def wait_for_waiter(pool, count=1, timeout=WAIT):
    """阻塞直到 pool 的条件变量上出现 count 个正在 wait 的线程。

    Condition 在持锁期间等待队列为空，借此可以确定竞争者已经进入
    cond.wait()（已释放锁、可被唤醒），从而把并发节奏定死。
    """
    deadline = time.monotonic() + timeout
    while True:
        with pool._cond:
            waiters = pool._cond._waiters  # CPython Condition 内部双向队列
            n = 0 if waiters is None else len(waiters)
        if n >= count:
            return
        if time.monotonic() >= deadline:
            raise AssertionError("fewer than %d waiter(s) blocked within %.1fs" % (count, timeout))
        time.sleep(0.005)


class BorrowBasicTests(unittest.TestCase):
    """README 1：空闲直取、池未满新建。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    def test_borrow_creates_when_not_full(self):
        c1 = self.pool.borrow()
        c2 = self.pool.borrow()
        self.assertIsInstance(c1, FakeConn)
        self.assertIsNot(c1, c2)
        self.assertEqual(self.pool.stats()["created"], 2)
        self.assertEqual(self.pool.stats()["inflight"], 2)

    def test_borrow_takes_idle_first(self):
        c1 = self.pool.borrow()
        self.pool.return_conn(c1)
        c2 = self.pool.borrow()
        self.assertIs(c1, c2)
        self.assertEqual(self.pool.stats()["created"], 1)

    def test_borrow_timeout_raises_borrow_timeout(self):
        self.pool.borrow()
        self.pool.borrow()
        start = time.monotonic()
        with self.assertRaises(BorrowTimeout):
            self.pool.borrow(timeout=0.2)
        self.assertLess(time.monotonic() - start, WAIT)


class ReturnConnTests(unittest.TestCase):
    """README 2：归还与唤醒；异常归还路径。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    # 红用例。
    # README 期望：conn.healthy 为 False 的连接归还时立即 close() 并丢弃，
    #   绝不回到空闲队列；之后再 borrow 必须由 factory 新建连接。
    # 实际行为：return_conn 完全不检查 healthy，坏连接照常 append 进空闲
    #   队列并被下一个 borrow 取出，created 不增长（坏连接被二次发放）。
    def test_red_unhealthy_conn_closed_and_dropped_on_return(self):
        conn = self.pool.borrow()
        conn.healthy = False
        self.pool.return_conn(conn)
        self.assertTrue(conn.closed)
        self.assertEqual(self.pool.stats()["idle"], 0)
        again = self.pool.borrow()
        self.assertIsNot(again, conn)
        self.assertFalse(again.closed)
        self.assertEqual(self.pool.stats()["created"], 2)

    def test_return_foreign_conn_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.pool.return_conn(FakeConn())

    def test_return_same_conn_twice_raises_value_error(self):
        conn = self.pool.borrow()
        self.pool.return_conn(conn)
        with self.assertRaises(ValueError):
            self.pool.return_conn(conn)

    def test_return_wakes_single_waiter_immediately(self):
        # README 1 正面场景：池满后等待，一旦有连接归还，等待者应立即拿到，
        # 不应受 timeout 影响。
        holder = self.pool.borrow()
        self.pool.borrow()
        got = threading.Event()
        box = {}

        def waiter():
            box["conn"] = self.pool.borrow(timeout=WAIT)
            got.set()

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        wait_for_waiter(self.pool)
        self.pool.return_conn(holder)
        wait_for(got)
        t.join(WAIT)
        self.assertIs(box["conn"], holder)
        self.assertFalse(holder.closed)


class CloseTests(unittest.TestCase):
    """README 3：close 幂等、关空闲、唤醒等待者、丢弃在途归还。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def test_close_is_idempotent_and_closes_idle_conns(self):
        c1 = self.pool.borrow()
        c2 = self.pool.borrow()
        self.pool.return_conn(c1)
        self.pool.return_conn(c2)
        self.pool.close()
        self.assertTrue(c1.closed)
        self.assertTrue(c2.closed)
        self.pool.close()
        self.assertTrue(self.pool.stats()["closed"])

    def test_borrow_after_close_raises_pool_closed(self):
        self.pool.close()
        with self.assertRaises(PoolClosedError):
            self.pool.borrow()

    def test_inflight_conn_returned_after_close_is_closed_and_dropped(self):
        conn = self.pool.borrow()
        self.pool.close()
        self.pool.return_conn(conn)
        self.assertTrue(conn.closed)
        self.assertEqual(self.pool.stats()["idle"], 0)

    # 红用例。
    # README 期望：close() 必须立即唤醒所有在 borrow 中等待的调用方，它们
    #   立刻收到 PoolClosedError，不允许一直睡到自己的 timeout。
    # 实际行为：close() 只置 _closed、关空闲连接，没有 notify_all()；等待
    #   线程一直阻塞在 cond.wait(timeout)，直到超时才抛 BorrowTimeout（而
    #   非 PoolClosedError）。
    def test_red_close_wakes_waiting_borrow_immediately(self):
        self.pool.borrow()
        self.pool.borrow()
        errors = []
        started = threading.Event()

        def waiter():
            started.set()
            try:
                self.pool.borrow(timeout=30)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        wait_for(started)
        wait_for_waiter(self.pool)
        self.pool.close()
        t.join(IMMEDIATE)
        self.assertFalse(t.is_alive(), "waiting borrow was not woken by close()")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PoolClosedError)


class ConcurrentTests(unittest.TestCase):
    """真实多线程场景，Event 同步定死节奏。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=1, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    # 红用例。
    # README 期望：池满时两个等待者同时等待，只有一个连接归还时，其中一人
    #   立即拿到连接，另一人继续等待——任何等待者都不应被错误唤醒后抛
    #   BorrowTimeout（惊群/虚假唤醒）。
    # 实际行为：borrow 只 wait 一次且不再循环检查；notify_all 同时唤醒两人，
    #   抢到连接的一人拿走连接，没抢到的一人直接落到 borrow 末尾
    #   raise BorrowTimeout，尽管 deadline 远未到、池仍满。
    def test_red_one_returned_conn_serves_one_waiter_without_false_timeout(self):
        holder = self.pool.borrow()
        results = {}
        got = {1: threading.Event(), 2: threading.Event()}
        failed = {1: threading.Event(), 2: threading.Event()}

        def waiter(idx):
            try:
                results[idx] = self.pool.borrow(timeout=30)
                got[idx].set()
            except Exception:  # noqa: BLE001
                failed[idx].set()

        threads = [threading.Thread(target=waiter, args=(i,), daemon=True) for i in (1, 2)]
        for t in threads:
            t.start()
        wait_for_waiter(self.pool, count=2)

        released = threading.Event()

        def returner():
            self.pool.return_conn(holder)
            released.set()

        threading.Thread(target=returner, daemon=True).start()
        wait_for(released)

        # 归还一个连接后，等待者只会出现两种结果：拿到连接或失败。
        # 轮询到任一结果落地即停，随后留短窗口确认对侧线程无动作，
        # 节奏由事件决定；0.1s 仅为调度抖动余量，非逻辑判定依据。
        settle = time.monotonic() + WAIT
        while time.monotonic() < settle:
            if any(got[i].is_set() or failed[i].is_set() for i in (1, 2)):
                break
            time.sleep(0.005)
        self.assertLess(time.monotonic(), settle, "neither waiter settled after return")
        time.sleep(0.1)
        winners = [i for i in (1, 2) if got[i].is_set()]
        failed_idx = [i for i in (1, 2) if failed[i].is_set()]

        # README：恰好一人立即拿到连接，另一人继续等；谁赢由调度决定。
        self.assertEqual(len(winners), 1)
        self.assertEqual(failed_idx, [])
        loser = next(i for i in (1, 2) if i not in winners)

        # 未拿到的一人必须仍在正常等待，随后归还连接应立即拿到它。
        self.assertIs(results.get(winners[0]), holder)
        second = threading.Event()

        def return_winner():
            self.pool.return_conn(results[winners[0]])
            second.set()

        threading.Thread(target=return_winner, daemon=True).start()
        wait_for(second)
        wait_for(got[loser])
        self.assertFalse(failed[loser].is_set())

    def test_created_never_exceeds_max_size_under_contention(self):
        # README 4：高并发借还下创建总数恒不超过 max_size。
        pool = ConnectionPool(max_size=4, borrow_timeout=1.0)
        self.addCleanup(pool.close)
        rounds = 200
        n_threads = 12
        barrier = threading.Barrier(n_threads)
        errors = []

        def worker():
            barrier.wait()
            try:
                for _ in range(rounds):
                    conn = None
                    while conn is None:
                        try:
                            conn = pool.borrow(timeout=1.0)
                        except BorrowTimeout:
                            # 被缺陷行为误伤时重试，本用例只钉 created 上限。
                            continue
                    if pool.stats()["created"] > pool.max_size:
                        raise AssertionError("created exceeded max_size mid-run")
                    pool.return_conn(conn)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
            self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])
        stats = pool.stats()
        self.assertLessEqual(stats["created"], 4)
        self.assertEqual(stats["inflight"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
