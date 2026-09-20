"""预留、按实结算与超时回收的行为测试。"""
import threading
import unittest

from quota import (
    QuotaExceeded,
    QuotaPool,
    Reservation,
    ReservationExpired,
    ReservationNotFound,
)


class FakeClock:
    """可手动拨的单调时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestReserveSettle(unittest.TestCase):
    def test_reserve_freezes_quota(self):
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        self.assertIsInstance(reservation, Reservation)
        self.assertEqual(pool.reserved, 40)
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.available, 60)
        self.assertEqual(pool.available + pool.used + pool.reserved, pool.total)

    def test_reserve_over_capacity_raises(self):
        pool = QuotaPool(50, clock=FakeClock())
        pool.reserve(30, ttl=10)
        with self.assertRaises(QuotaExceeded):
            pool.reserve(21, ttl=10)
        self.assertEqual(pool.reserved, 30)
        self.assertEqual(pool.available, 20)

    def test_settle_full_consumption_keeps_quota(self):
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        refunded = pool.settle(reservation, 40)
        self.assertEqual(refunded, 0)
        self.assertEqual(pool.used, 40)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.available, 60)

    def test_settle_partial_consumption_refunds_remainder(self):
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        refunded = pool.settle(reservation, 20)
        self.assertEqual(refunded, 20)
        self.assertEqual(pool.used, 20)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.available, 80)

    def test_settle_zero_consumption_refunds_all(self):
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        self.assertEqual(pool.settle(reservation, 0), 40)
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.available, 100)

    def test_duplicate_settle_refunds_once(self):
        """重试组件和解算器各结算一次：第二次幂等，不重复退还。"""
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        self.assertEqual(pool.settle(reservation, 10), 30)
        self.assertEqual(pool.settle(reservation, 10), 0)
        self.assertEqual(pool.settle(reservation, 40), 0)
        self.assertEqual(pool.used, 10)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.available, 90)

    def test_settle_consumed_over_reserved_raises_and_leaves_accounts(self):
        """退还额不能为负：消耗超过预留直接报错，账目不动。"""
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        with self.assertRaises(ValueError):
            pool.settle(reservation, 41)
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.reserved, 40)
        self.assertEqual(pool.available, 60)
        # 报错后用合法消耗仍能正常结算
        self.assertEqual(pool.settle(reservation, 40), 0)
        self.assertEqual(pool.used, 40)

    def test_settle_negative_consumed_raises(self):
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        with self.assertRaises(ValueError):
            pool.settle(reservation, -1)

    def test_settle_non_numeric_consumed_raises(self):
        pool = QuotaPool(100, clock=FakeClock())
        reservation = pool.reserve(40, ttl=10)
        with self.assertRaises(TypeError):
            pool.settle(reservation, True)
        with self.assertRaises(TypeError):
            pool.settle(reservation, "10")

    def test_invalid_handle_raises(self):
        pool = QuotaPool(100, clock=FakeClock())
        other = QuotaPool(100, clock=FakeClock())
        foreign = other.reserve(10, ttl=10)
        with self.assertRaises(ReservationNotFound):
            pool.settle(foreign, 5)
        with self.assertRaises(TypeError):
            pool.settle("not-a-reservation", 5)

    def test_reserve_validates_amount_and_ttl(self):
        pool = QuotaPool(100, clock=FakeClock())
        with self.assertRaises(ValueError):
            pool.reserve(0, ttl=10)
        with self.assertRaises(ValueError):
            pool.reserve(10, ttl=0)
        with self.assertRaises(ValueError):
            pool.reserve(10, ttl=-1)
        with self.assertRaises(TypeError):
            pool.reserve(1.5, ttl=10)
        with self.assertRaises(TypeError):
            pool.reserve(10, ttl=True)
        with self.assertRaises(TypeError):
            QuotaPool(100, clock=123)

    def test_acquire_shares_pool_with_reserved(self):
        pool = QuotaPool(100, clock=FakeClock())
        pool.reserve(60, ttl=10)
        pool.acquire(30)
        self.assertEqual(pool.available, 10)
        with self.assertRaises(QuotaExceeded):
            pool.acquire(11)
        with self.assertRaises(QuotaExceeded):
            pool.reserve(11, ttl=10)


class TestTimeoutReclaim(unittest.TestCase):
    def test_reap_returns_expired_quota(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        pool.reserve(40, ttl=10)
        clock.advance(9)
        self.assertEqual(pool.reap_expired(), 0)
        self.assertEqual(pool.reserved, 40)
        clock.advance(1)
        self.assertEqual(pool.reap_expired(), 40)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.available, 100)

    def test_reap_is_idempotent(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        pool.reserve(40, ttl=10)
        clock.advance(10)
        self.assertEqual(pool.reap_expired(), 40)
        self.assertEqual(pool.reap_expired(), 0)

    def test_settle_after_expiry_raises(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        reservation = pool.reserve(40, ttl=10)
        clock.advance(10)
        with self.assertRaises(ReservationExpired):
            pool.settle(reservation, 10)
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.available, 100)

    def test_expired_settle_and_reap_do_not_double_refund(self):
        """结算与超时回收撞车：谁先处理谁生效，额度只回一次。"""
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        reservation = pool.reserve(40, ttl=10)
        clock.advance(10)
        # settle 检测到过期，内部完成回收并报错
        with self.assertRaises(ReservationExpired):
            pool.settle(reservation, 10)
        # 再扫描不能再回收一次
        self.assertEqual(pool.reap_expired(), 0)
        self.assertEqual(pool.available, 100)

    def test_reap_only_affects_expired_reservations(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        old = pool.reserve(20, ttl=5)
        young = pool.reserve(30, ttl=20)
        clock.advance(10)
        self.assertEqual(pool.reap_expired(), 20)
        self.assertEqual(pool.reserved, 30)
        self.assertEqual(pool.settle(young, 10), 20)
        self.assertEqual(pool.used, 10)
        with self.assertRaises(ReservationExpired):
            pool.settle(old, 5)

    def test_reserve_reaps_expired_before_capacity_check(self):
        """申请完再没消息的预留超时后，新预留能拿回那部分额度。"""
        clock = FakeClock()
        pool = QuotaPool(50, clock=clock)
        pool.reserve(50, ttl=10)
        self.assertEqual(pool.available, 0)
        clock.advance(10)
        new = pool.reserve(50, ttl=10)
        self.assertEqual(pool.reserved, 50)
        self.assertEqual(pool.available, 0)
        self.assertEqual(pool.settle(new, 0), 50)
        self.assertEqual(pool.available, 50)


class TestConcurrency(unittest.TestCase):
    def test_duplicate_settle_under_threads_refunds_once(self):
        pool = QuotaPool(1000, clock=FakeClock())
        reservation = pool.reserve(100, ttl=100)
        results = []

        def worker():
            try:
                results.append(pool.settle(reservation, 10))
            except ReservationError:
                results.append(-1)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), [0] * 19 + [90])
        self.assertEqual(pool.used, 10)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.available + pool.used, pool.total)

    def test_settle_and_reap_race_keeps_balanced_books(self):
        """结算与回收并发对撞，账目恒等式始终成立，退还不超过预留。"""
        clock = FakeClock()
        pool = QuotaPool(1000, clock=clock)
        reservations = [pool.reserve(10, ttl=10) for _ in range(50)]
        settled = {"count": 0}
        expired = {"count": 0}
        counter_lock = threading.Lock()

        def settle_worker(reservation):
            try:
                pool.settle(reservation, 4)
                with counter_lock:
                    settled["count"] += 1
            except ReservationExpired:
                with counter_lock:
                    expired["count"] += 1

        clock.advance(10)
        threads = []
        for reservation in reservations:
            threads.append(
                threading.Thread(target=settle_worker, args=(reservation,))
            )
            threads.append(threading.Thread(target=pool.reap_expired))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(settled["count"] + expired["count"], 50)
        self.assertEqual(pool.reserved, 0)
        self.assertEqual(pool.used, settled["count"] * 4)
        self.assertEqual(pool.available, 1000 - settled["count"] * 4)
        self.assertEqual(pool.available + pool.used, pool.total)

    def test_background_reaper_reclaims_automatically(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        pool.reserve(40, ttl=10)
        pool.start_reaper(interval=0.01)
        try:
            clock.advance(10)
            for _ in range(200):
                if pool.reserved == 0:
                    break
                threading.Event().wait(0.01)
            self.assertEqual(pool.reserved, 0)
            self.assertEqual(pool.available, 100)
        finally:
            pool.stop_reaper()


if __name__ == "__main__":
    unittest.main()
