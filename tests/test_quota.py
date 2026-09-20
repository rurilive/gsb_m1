"""QuotaPool 行为基线。"""
import threading
import unittest

from quota import QuotaExceeded, QuotaPool


class TestQuotaPool(unittest.TestCase):
    def test_acquire_reduces_available(self):
        pool = QuotaPool(100)
        pool.acquire(30)
        self.assertEqual(pool.available, 70)
        self.assertEqual(pool.used, 30)

    def test_available_plus_used_equals_total(self):
        pool = QuotaPool(100)
        pool.acquire(40)
        self.assertEqual(pool.available + pool.used, pool.total)

    def test_exact_capacity_succeeds(self):
        pool = QuotaPool(10)
        pool.acquire(10)
        self.assertEqual(pool.available, 0)
        with self.assertRaises(QuotaExceeded):
            pool.acquire(1)

    def test_over_capacity_raises(self):
        pool = QuotaPool(50)
        with self.assertRaises(QuotaExceeded):
            pool.acquire(51)

    def test_over_capacity_leaves_state_untouched(self):
        pool = QuotaPool(50)
        pool.acquire(20)
        with self.assertRaises(QuotaExceeded):
            pool.acquire(31)
        self.assertEqual(pool.used, 20)
        self.assertEqual(pool.available, 30)

    def test_non_positive_amount_raises(self):
        pool = QuotaPool(10)
        with self.assertRaises(ValueError):
            pool.acquire(0)
        with self.assertRaises(ValueError):
            pool.acquire(-5)

    def test_non_integer_amount_raises(self):
        pool = QuotaPool(10)
        with self.assertRaises(TypeError):
            pool.acquire(1.5)

    def test_negative_total_raises(self):
        with self.assertRaises(ValueError):
            QuotaPool(-1)

    def test_utilisation(self):
        pool = QuotaPool(100)
        pool.acquire(25)
        self.assertAlmostEqual(pool.utilisation(), 0.25)
        self.assertEqual(QuotaPool(0).utilisation(), 0.0)

    def test_acquire_is_atomic_under_threads(self):
        pool = QuotaPool(1000)
        granted = []

        def worker():
            for _ in range(20):
                try:
                    pool.acquire(1)
                    granted.append(1)
                except QuotaExceeded:
                    pass

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(pool.used, 200)
        self.assertEqual(len(granted), 200)
        self.assertEqual(pool.available + pool.used, pool.total)


if __name__ == "__main__":
    unittest.main()
