"""QuotaPool 预留/结算/超时回收行为。"""
import threading
import unittest

from quota import QuotaExceeded, QuotaPool


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestReserve(unittest.TestCase):
    def test_reserve_reduces_available(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        self.assertEqual(pool.used, 40)
        self.assertEqual(pool.available, 60)
        self.assertEqual(pool.reservation_state(reservation_id), "open")

    def test_reserve_over_capacity_raises(self):
        pool = QuotaPool(50)
        pool.reserve(50)
        with self.assertRaises(QuotaExceeded):
            pool.reserve(1)

    def test_reserve_validates_amount(self):
        pool = QuotaPool(10)
        with self.assertRaises(ValueError):
            pool.reserve(0)
        with self.assertRaises(ValueError):
            pool.reserve(-3)
        with self.assertRaises(TypeError):
            pool.reserve(1.5)

    def test_settle_full_consumption_refunds_nothing(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        self.assertEqual(pool.settle(reservation_id, 40), 0)
        self.assertEqual(pool.used, 40)
        self.assertEqual(pool.reservation_state(reservation_id), "settled")

    def test_settle_partial_consumption_refunds_difference(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        self.assertEqual(pool.settle(reservation_id, 15), 25)
        self.assertEqual(pool.used, 15)
        self.assertEqual(pool.available, 85)

    def test_settle_zero_consumption_refunds_everything(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        self.assertEqual(pool.settle(reservation_id, 0), 40)
        self.assertEqual(pool.used, 0)

    def test_duplicate_settle_is_idempotent(self):
        # 重试组件和解算器各结算一次，额度不能退超。
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        self.assertEqual(pool.settle(reservation_id, 15), 25)
        self.assertEqual(pool.settle(reservation_id, 15), 0)
        self.assertEqual(pool.settle(reservation_id, 0), 0)
        self.assertEqual(pool.used, 15)
        self.assertEqual(pool.available, 85)

    def test_settle_above_reserved_raises_and_keeps_state(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        with self.assertRaises(ValueError):
            pool.settle(reservation_id, 41)
        self.assertEqual(pool.used, 40)
        self.assertEqual(pool.reservation_state(reservation_id), "open")
        self.assertEqual(pool.settle(reservation_id, 40), 0)

    def test_settle_validates_actual(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(10)
        with self.assertRaises(ValueError):
            pool.settle(reservation_id, -1)
        with self.assertRaises(TypeError):
            pool.settle(reservation_id, 1.5)

    def test_settle_unknown_reservation_raises(self):
        pool = QuotaPool(100)
        with self.assertRaises(KeyError):
            pool.settle(999, 0)


class TestReservationTimeout(unittest.TestCase):
    def test_expired_reservation_is_reclaimed(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock, reservation_timeout=30)
        reservation_id = pool.reserve(40)
        clock.advance(31)
        self.assertEqual(pool.reclaim_expired(), [reservation_id])
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.available, 100)
        self.assertEqual(pool.reservation_state(reservation_id), "expired")

    def test_timeout_boundary_is_exact(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock, reservation_timeout=30)
        pool.reserve(40)
        clock.advance(29.9)
        self.assertEqual(pool.reclaim_expired(), [])
        self.assertEqual(pool.used, 40)
        clock.advance(0.1)
        self.assertEqual(len(pool.reclaim_expired()), 1)
        self.assertEqual(pool.used, 0)

    def test_reclaim_only_touches_expired(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock, reservation_timeout=30)
        old = pool.reserve(10)
        clock.advance(31)
        fresh = pool.reserve(20)  # 惰性回收顺带收回 old
        self.assertEqual(pool.reclaim_expired(), [])
        self.assertEqual(pool.reservation_state(old), "expired")
        self.assertEqual(pool.used, 20)
        self.assertEqual(pool.reservation_state(fresh), "open")

    def test_settle_after_expiry_does_not_double_refund(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock, reservation_timeout=30)
        reservation_id = pool.reserve(40)
        clock.advance(31)
        pool.reclaim_expired()
        self.assertEqual(pool.settle(reservation_id, 10), 0)
        self.assertEqual(pool.used, 0)
        self.assertEqual(pool.available, 100)

    def test_no_timeout_means_no_expiry(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock)
        pool.reserve(40)
        clock.advance(10 ** 9)
        self.assertEqual(pool.reclaim_expired(), [])
        self.assertEqual(pool.used, 40)

    def test_acquire_and_reserve_trigger_lazy_reclaim(self):
        clock = FakeClock()
        pool = QuotaPool(100, clock=clock, reservation_timeout=30)
        pool.reserve(100)
        clock.advance(31)
        pool.acquire(60)  # 惰性回收先发生，否则这里会抛 QuotaExceeded
        self.assertEqual(pool.used, 60)

    def test_invalid_timeout_raises(self):
        with self.assertRaises(ValueError):
            QuotaPool(10, reservation_timeout=0)


class TestReserveConcurrency(unittest.TestCase):
    def test_settle_and_reclaim_race_stays_consistent(self):
        # 结算与超时回收并发对撞：无论谁先生效，总额账必须守恒。
        for _ in range(50):
            clock = FakeClock()
            pool = QuotaPool(100, clock=clock, reservation_timeout=30)
            reservation_id = pool.reserve(40)
            clock.advance(31)
            barrier = threading.Barrier(2)

            def do_settle():
                barrier.wait()
                pool.settle(reservation_id, 15)

            def do_reclaim():
                barrier.wait()
                pool.reclaim_expired()

            threads = [
                threading.Thread(target=do_settle),
                threading.Thread(target=do_reclaim),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertIn(pool.used, (0, 15))
            self.assertEqual(pool.available + pool.used, pool.total)
            self.assertNotEqual(pool.reservation_state(reservation_id), "open")

    def test_concurrent_settle_from_retry_and_solver(self):
        pool = QuotaPool(100)
        reservation_id = pool.reserve(40)
        barrier = threading.Barrier(2)

        def do_settle():
            barrier.wait()
            pool.settle(reservation_id, 15)

        threads = [threading.Thread(target=do_settle) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(pool.used, 15)
        self.assertEqual(pool.available, 85)


if __name__ == "__main__":
    unittest.main()
