"""FenceGuard 现有行为的锁定测试，基线不许动。"""

import threading
import unittest

from leasekeeper.fence import FenceGuard, StaleFence


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.guard = FenceGuard()

    def test_increasing_tokens_pass(self):
        self.assertTrue(self.guard.check("r", 1))
        self.assertTrue(self.guard.check("r", 2))
        self.assertEqual(self.guard.high_water("r"), 2)

    def test_equal_token_replay_passes(self):
        self.guard.check("r", 5)
        self.assertTrue(self.guard.check("r", 5))

    def test_lower_token_raises_and_water_stays(self):
        self.guard.check("r", 5)
        with self.assertRaises(StaleFence):
            self.guard.check("r", 4)
        self.assertEqual(self.guard.high_water("r"), 5)

    def test_unknown_resource_starts_at_zero(self):
        self.assertEqual(self.guard.high_water("ghost"), 0)
        self.assertTrue(self.guard.check("ghost", 1))

    def test_resources_are_independent(self):
        self.guard.check("a", 10)
        self.assertTrue(self.guard.check("b", 3))
        self.assertEqual(self.guard.high_water("b"), 3)

    def test_token_must_be_positive_int(self):
        with self.assertRaises(ValueError):
            self.guard.check("r", 0)
        with self.assertRaises(ValueError):
            self.guard.check("r", -3)
        with self.assertRaises(ValueError):
            self.guard.check("r", 1.5)


class SealTest(unittest.TestCase):
    def setUp(self):
        self.guard = FenceGuard()

    def test_seal_raises_high_water(self):
        self.assertEqual(self.guard.seal("r", 42), 42)
        self.assertEqual(self.guard.high_water("r"), 42)
        self.assertTrue(self.guard.check("r", 42))
        with self.assertRaises(StaleFence):
            self.guard.check("r", 41)

    def test_seal_never_rolls_back(self):
        self.guard.seal("r", 42)
        self.assertEqual(self.guard.seal("r", 10), 42)
        with self.assertRaises(StaleFence):
            self.guard.check("r", 10)

    def test_seal_then_higher_token_passes(self):
        self.guard.seal("r", 42)
        self.assertTrue(self.guard.check("r", 43))
        self.assertEqual(self.guard.high_water("r"), 43)

    def test_seal_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            self.guard.seal("r", -1)
        with self.assertRaises(ValueError):
            self.guard.seal("r", 0)


class ConcurrencyTest(unittest.TestCase):
    def test_parallel_streams_on_own_resources_never_stale(self):
        guard = FenceGuard()
        threads = 4
        per_thread = 500

        def work(index):
            resource = "res-%d" % index
            for step in range(per_thread):
                guard.check(resource, 1000 + step)

        workers = [
            threading.Thread(target=work, args=(i,)) for i in range(threads)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        for index in range(threads):
            self.assertEqual(
                guard.high_water("res-%d" % index), 1000 + per_thread - 1
            )


if __name__ == "__main__":
    unittest.main()
