"""netpool 语义测试：以 README.md 的"语义约定"为正式行为定义，逐条锁定。

运行方式（仓库根目录下）：
    python3 -m unittest discover -s tests -v
    python3 tests/test_pool.py
"""

import os
import queue
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


class TestBorrowSemantics(unittest.TestCase):
    """README 第 1 条：borrow 的取空闲 / 新建 / 超时 / 关闭语义。"""

    def test_borrow_marks_inflight_and_reuses_idle_conn(self):
        # 有空闲连接 → 直接取出并标记为在途；不新建
        pool = ConnectionPool(max_size=3)
        conn = pool.borrow()
        stats = pool.stats()
        self.assertEqual(stats["inflight"], 1)
        self.assertEqual(stats["idle"], 0)
        self.assertEqual(stats["created"], 1)

        pool.return_conn(conn)
        again = pool.borrow()
        self.assertIs(again, conn)
        stats = pool.stats()
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["inflight"], 1)
        self.assertEqual(stats["idle"], 0)

    def test_borrow_creates_new_conn_until_max_size(self):
        # 无空闲但池未满 → 用 factory 新建
        pool = ConnectionPool(max_size=2)
        first = pool.borrow()
        second = pool.borrow()
        self.assertIsNot(first, second)
        stats = pool.stats()
        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["inflight"], 2)

    def test_borrow_timeout_raises_borrowtimeout_near_deadline(self):
        # 池满且一直没人归还 → 到 deadline 抛 BorrowTimeout（不许提前也不许无限等）
        pool = ConnectionPool(max_size=1)
        pool.borrow()  # 占满
        started = time.monotonic()
        with self.assertRaises(BorrowTimeout):
            pool.borrow(timeout=0.3)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.2)  # 不得明显提前
        self.assertLess(elapsed, 1.5)  # 也不许赖着不走

    def test_borrow_after_close_raises_poolclosed(self):
        # 池已关闭 → 抛 PoolClosedError
        pool = ConnectionPool(max_size=1)
        pool.close()
        with self.assertRaises(PoolClosedError):
            pool.borrow()


class TestReturnSemantics(unittest.TestCase):
    """README 第 2 条：return_conn 的归还 / 唤醒 / 非法连接语义。"""

    def test_return_conn_not_from_pool_raises_valueerror(self):
        # 归还非本池借出的连接 → ValueError；重复归还同样非法
        pool = ConnectionPool(max_size=2)
        with self.assertRaises(ValueError):
            pool.return_conn(FakeConn())
        conn = pool.borrow()
        pool.return_conn(conn)
        with self.assertRaises(ValueError):
            pool.return_conn(conn)

    def test_return_conn_wakes_waiting_borrower(self):
        # 并发：等待中的 borrower 应在连接归还后立刻被唤醒并拿到它
        pool = ConnectionPool(max_size=1, borrow_timeout=5.0)
        held = pool.borrow()
        results = queue.Queue()

        def waiter():
            try:
                results.put(("conn", pool.borrow()))
            except Exception as exc:  # noqa: BLE001
                results.put(("exc", exc))

        thread = threading.Thread(target=waiter)
        thread.start()
        time.sleep(0.2)  # 留足余量，确保 waiter 已进入等待
        pool.return_conn(held)

        kind, payload = results.get(timeout=1.5)
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(kind, "conn", "等待者应被唤醒拿到连接，而不是拿到 %r" % (payload,))
        self.assertIs(payload, held)

    # RED（已知缺陷）：
    #   README 期望（第 2 条）：conn.healthy 为 False 的连接，归还时应立即 close()
    #     并丢弃，绝不回到空闲队列；下一次 borrow 应拿到新建连接。
    #   实际发生：return_conn 完全不检查 healthy，死连接原样进 _idle 且不 close()，
    #     下一次 borrow 把这条死连接又发了出去。
    def test_unhealthy_conn_is_closed_and_discarded_on_return(self):
        pool = ConnectionPool(max_size=2)
        conn = pool.borrow()
        conn.healthy = False  # 下游健康探测判死
        pool.return_conn(conn)

        self.assertTrue(conn.closed, "healthy=False 的连接归还后必须立即 close()")
        self.assertEqual(pool.stats()["idle"], 0, "死连接绝不许回到空闲队列")

        replacement = pool.borrow()
        self.assertIsNot(replacement, conn, "死连接被丢弃后应新建连接补位")


class TestCloseSemantics(unittest.TestCase):
    """README 第 3 条：close 的幂等 / 关空闲 / 唤醒等待者 / 在途回收语义。"""

    def test_close_is_idempotent_and_closes_idle_conns(self):
        pool = ConnectionPool(max_size=2)
        first = pool.borrow()
        second = pool.borrow()
        pool.return_conn(first)
        pool.return_conn(second)

        pool.close()
        pool.close()  # 幂等：第二次不抛错

        self.assertTrue(first.closed)
        self.assertTrue(second.closed)
        self.assertTrue(pool.stats()["closed"])

    def test_inflight_conn_returned_after_close_is_closed_and_dropped(self):
        # 在途连接随后归还时：直接 close() 丢弃，不进池
        pool = ConnectionPool(max_size=1)
        conn = pool.borrow()
        pool.close()
        pool.return_conn(conn)  # 不抛错
        self.assertTrue(conn.closed)
        self.assertEqual(pool.stats()["idle"], 0)

    # RED（已知缺陷）：
    #   README 期望（第 3 条）：正在 borrow 中等待的调用方必须立即收到
    #     PoolClosedError，不允许等到超时。
    #   实际发生：close() 只置标志、关空闲连接，从不 notify 条件变量；等待者
    #     一直睡到 timeout 才醒，最后拿到的是 BorrowTimeout 而不是 PoolClosedError。
    def test_close_wakes_waiting_borrower_immediately(self):
        pool = ConnectionPool(max_size=1, borrow_timeout=5.0)
        pool.borrow()  # 占满，让 waiter 必然阻塞
        results = queue.Queue()

        def waiter():
            try:
                pool.borrow(timeout=1.5)
                results.put(("conn", None))
            except Exception as exc:  # noqa: BLE001
                results.put(("exc", exc))

        thread = threading.Thread(target=waiter, daemon=True)
        thread.start()
        time.sleep(0.2)  # 留足余量，确保 waiter 已进入等待

        pool.close()
        thread.join(timeout=0.8)  # “立即”的宽限：0.8s 内必须结束（timeout 是 1.5s）
        try:
            self.assertFalse(
                thread.is_alive(),
                "close() 后等待中的 borrow 必须立即退出，而不是睡到超时",
            )
            kind, payload = results.get(timeout=0.5)
            self.assertEqual(kind, "exc")
            self.assertIsInstance(payload, PoolClosedError)
        finally:
            thread.join(timeout=2.0)


class TestConcurrencySemantics(unittest.TestCase):
    """README 第 1、4 条在真实并发下的表现。"""

    # RED（已知缺陷）：
    #   README 期望（第 1 条）：池满时等待归还，"等待期间只要有连接归还，应立即
    #     拿到它"，到 deadline 仍没有才抛 BorrowTimeout。即：多个等待者抢一个
    #     归还的连接时，没抢到的应继续等到 deadline，期间再有归还照样能拿到。
    #   实际发生：borrow 只 wait() 一次、没有循环重查。两个等待者被 notify_all
    #     同时唤醒而连接只够一个时，没抢到的那个在 deadline 之前就直接抛
    #     BorrowTimeout，之后再有连接归还也与它无关了。
    def test_waiter_keeps_waiting_when_it_misses_a_wakeup(self):
        pool = ConnectionPool(max_size=1, borrow_timeout=5.0)
        held = pool.borrow()
        results = queue.Queue()

        def waiter():
            try:
                results.put(("conn", pool.borrow(timeout=2.0)))
            except Exception as exc:  # noqa: BLE001
                results.put(("exc", exc))

        threads = [threading.Thread(target=waiter) for _ in range(2)]
        for thread in threads:
            thread.start()
        time.sleep(0.3)  # 留足余量，确保两个 waiter 都已进入等待

        pool.return_conn(held)  # 同时唤醒两个 waiter，只有一个能拿到
        kind_first, payload_first = results.get(timeout=2.0)
        if kind_first == "conn":
            # 赢家用完了归还，输家应当还在等、并能拿到这第二次归还
            pool.return_conn(payload_first)
        kind_second, payload_second = results.get(timeout=2.0)
        if kind_second == "conn":
            pool.return_conn(payload_second)
        for thread in threads:
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive())

        self.assertEqual(
            (kind_first, kind_second),
            ("conn", "conn"),
            "两个等待者都应最终拿到连接；实际结果：%r / %r"
            % ((kind_first, payload_first), (kind_second, payload_second)),
        )

    def test_concurrent_stress_created_capped_and_stats_consistent(self):
        # README 第 4 条：created <= max_size；且并发借还后账目自洽
        worker_count = 8
        rounds = 30
        pool = ConnectionPool(max_size=3, borrow_timeout=5.0)
        start = threading.Event()
        errors = []

        def worker():
            start.wait()
            try:
                for _ in range(rounds):
                    conn = pool.borrow()
                    pool.return_conn(conn)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        start.set()  # 统一起跑，制造真实竞争
        for thread in threads:
            thread.join(timeout=10.0)
            self.assertFalse(thread.is_alive(), "worker 卡死了")

        self.assertEqual(errors, [])
        stats = pool.stats()
        self.assertLessEqual(stats["created"], 3, "created 总数不得超过 max_size")
        self.assertEqual(stats["inflight"], 0)
        self.assertEqual(stats["idle"], stats["created"])


if __name__ == "__main__":
    unittest.main()
