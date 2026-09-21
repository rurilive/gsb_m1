"""LeaseKeeper 现有行为的锁定测试，基线不许动。"""

import threading
import unittest

from leasekeeper.clock import FakeClock
from leasekeeper.keeper import KeeperStats, Lease, LeaseConflict, LeaseKeeper


class GrantTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=1000.0)
        self.keeper = LeaseKeeper(clock=self.clock.current)

    def test_grant_returns_lease_with_fields(self):
        lease = self.keeper.grant("db.primary", "n1", 30.0)
        self.assertIsInstance(lease, Lease)
        self.assertEqual(lease.lease_id, "L000001")
        self.assertEqual(lease.resource, "db.primary")
        self.assertEqual(lease.holder, "n1")
        self.assertEqual(lease.token, 1)
        self.assertEqual(lease.ttl, 30.0)
        self.assertEqual(lease.expires_at, 1030.0)

    def test_tokens_increase_per_grant(self):
        first = self.keeper.grant("a", "n1")
        second = self.keeper.grant("b", "n2")
        self.assertEqual(first.token, 1)
        self.assertEqual(second.token, 2)
        self.assertEqual(self.keeper.stats().last_token, 2)

    def test_conflict_while_active(self):
        self.keeper.grant("db.primary", "n1")
        with self.assertRaises(LeaseConflict):
            self.keeper.grant("db.primary", "n2")
        stats = self.keeper.stats()
        self.assertEqual(stats.conflicts, 1)
        self.assertEqual(stats.grants, 1)
        self.assertEqual(self.keeper.get("db.primary").holder, "n1")

    def test_alive_right_before_expiry(self):
        self.keeper.grant("db.primary", "n1", 5.0)
        self.clock.advance(4.999)
        with self.assertRaises(LeaseConflict):
            self.keeper.grant("db.primary", "n2")

    def test_regrant_at_exact_expiry_gets_next_token(self):
        self.keeper.grant("db.primary", "n1", 5.0)
        self.clock.advance(5.0)
        lease = self.keeper.grant("db.primary", "n2", 5.0)
        self.assertEqual(lease.token, 2)
        self.assertEqual(self.keeper.stats().reclaims, 1)

    def test_ttl_must_be_positive(self):
        with self.assertRaises(ValueError):
            self.keeper.grant("db.primary", "n1", 0.0)


class RenewTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=1000.0)
        self.keeper = LeaseKeeper(clock=self.clock.current)

    def test_renew_extends_from_now_with_original_ttl(self):
        lease = self.keeper.grant("r", "n1", 10.0)
        self.clock.advance(4.0)
        renewed = self.keeper.renew(lease.lease_id, "n1")
        self.assertEqual(renewed.lease_id, lease.lease_id)
        self.assertEqual(renewed.ttl, 10.0)
        self.assertEqual(renewed.expires_at, 1014.0)
        self.assertEqual(self.keeper.stats().renews, 1)

    def test_renew_with_explicit_ttl_replaces_span(self):
        lease = self.keeper.grant("r", "n1", 10.0)
        self.clock.advance(4.0)
        renewed = self.keeper.renew(lease.lease_id, "n1", 2.0)
        self.assertEqual(renewed.ttl, 2.0)
        self.assertEqual(renewed.expires_at, 1006.0)

    def test_renew_unknown_id_is_none(self):
        self.assertIsNone(self.keeper.renew("L999999", "n1"))

    def test_renew_wrong_holder_is_none_and_lease_stays(self):
        lease = self.keeper.grant("r", "n1")
        self.assertIsNone(self.keeper.renew(lease.lease_id, "n2"))
        self.assertEqual(self.keeper.get("r").holder, "n1")

    def test_renew_after_expiry_is_none_and_purges(self):
        lease = self.keeper.grant("r", "n1", 5.0)
        self.clock.advance(5.0)
        self.assertIsNone(self.keeper.renew(lease.lease_id, "n1"))
        self.assertIsNone(self.keeper.get("r"))
        self.assertEqual(self.keeper.stats().reclaims, 1)

    def test_renew_rejects_non_positive_ttl(self):
        lease = self.keeper.grant("r", "n1")
        with self.assertRaises(ValueError):
            self.keeper.renew(lease.lease_id, "n1", 0.0)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.keeper = LeaseKeeper()

    def test_release_by_holder(self):
        lease = self.keeper.grant("r", "n1")
        self.assertTrue(self.keeper.release(lease.lease_id, "n1"))
        self.assertIsNone(self.keeper.get("r"))
        self.assertEqual(self.keeper.stats().releases, 1)

    def test_release_twice_second_is_false(self):
        lease = self.keeper.grant("r", "n1")
        self.assertTrue(self.keeper.release(lease.lease_id, "n1"))
        self.assertFalse(self.keeper.release(lease.lease_id, "n1"))

    def test_release_by_stranger_is_false_and_lease_stays(self):
        lease = self.keeper.grant("r", "n1")
        self.assertFalse(self.keeper.release(lease.lease_id, "n2"))
        self.assertEqual(self.keeper.get("r").holder, "n1")

    def test_release_unknown_is_false(self):
        self.assertFalse(self.keeper.release("L999999", "n1"))

    def test_resource_freed_by_release_is_grantable(self):
        lease = self.keeper.grant("r", "n1")
        self.keeper.release(lease.lease_id, "n1")
        self.assertEqual(self.keeper.grant("r", "n2").token, 2)


class SweepTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=1000.0)
        self.keeper = LeaseKeeper(clock=self.clock.current)

    def test_get_returns_none_after_expiry_and_purges(self):
        self.keeper.grant("r", "n1", 5.0)
        self.clock.advance(5.0)
        self.assertIsNone(self.keeper.get("r"))
        self.assertEqual(self.keeper.resources(), [])
        self.assertEqual(self.keeper.stats().reclaims, 1)

    def test_sweep_returns_only_expired_sorted(self):
        self.keeper.grant("b", "n1", 5.0)
        self.keeper.grant("a", "n2", 20.0)
        self.keeper.grant("c", "n3", 5.0)
        self.clock.advance(6.0)
        dead = self.keeper.sweep()
        self.assertEqual([l.resource for l in dead], ["b", "c"])
        self.assertEqual(self.keeper.resources(), ["a"])
        self.assertEqual(self.keeper.stats().reclaims, 2)

    def test_sweep_with_nothing_dead_is_empty(self):
        self.keeper.grant("a", "n1", 5.0)
        self.clock.advance(1.0)
        self.assertEqual(self.keeper.sweep(), [])

    def test_sweep_boundary_exact_expiry_reclaimed(self):
        self.keeper.grant("a", "n1", 5.0)
        self.clock.advance(5.0)
        self.assertEqual(len(self.keeper.sweep()), 1)

    def test_released_lease_is_not_swept_again(self):
        lease = self.keeper.grant("a", "n1", 5.0)
        self.keeper.release(lease.lease_id, "n1")
        self.clock.advance(6.0)
        self.assertEqual(self.keeper.sweep(), [])
        self.assertEqual(self.keeper.stats().reclaims, 0)


class StatsTest(unittest.TestCase):
    def test_stats_counts_everything(self):
        clock = FakeClock(start=1000.0)
        keeper = LeaseKeeper(clock=clock.current)
        lease = keeper.grant("a", "n1")
        try:
            keeper.grant("a", "n2")
        except LeaseConflict:
            pass
        keeper.renew(lease.lease_id, "n1")
        keeper.release(lease.lease_id, "n1")
        stats = keeper.stats()
        self.assertIsInstance(stats, KeeperStats)
        self.assertEqual(
            (stats.grants, stats.conflicts, stats.renews, stats.releases),
            (1, 1, 1, 1),
        )
        self.assertEqual(stats.reclaims, 0)
        self.assertEqual(stats.active, 0)
        self.assertEqual(stats.last_token, 1)

    def test_active_counts_only_alive_leases(self):
        clock = FakeClock()
        keeper = LeaseKeeper(clock=clock.current)
        keeper.grant("a", "n1", 5.0)
        keeper.grant("b", "n2", 50.0)
        clock.advance(10.0)
        self.assertEqual(keeper.stats().active, 1)


class ConcurrencyTest(unittest.TestCase):
    def test_parallel_grants_on_distinct_resources_number_all_tokens(self):
        keeper = LeaseKeeper()
        threads = 8
        per_thread = 25
        results = {}

        def work(index):
            tokens = []
            for step in range(per_thread):
                lease = keeper.grant(
                    "res-%d-%d" % (index, step), "n%d" % index, 60.0
                )
                tokens.append(lease.token)
            results[index] = tokens

        workers = [
            threading.Thread(target=work, args=(i,)) for i in range(threads)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        merged = sorted(
            token for tokens in results.values() for token in tokens
        )
        self.assertEqual(merged, list(range(1, threads * per_thread + 1)))
        self.assertEqual(len(keeper.resources()), threads * per_thread)

    def test_race_on_same_resource_yields_single_winner(self):
        keeper = LeaseKeeper()
        contenders = 4
        barrier = threading.Barrier(contenders)
        outcomes = []
        lock = threading.Lock()

        def contend(index):
            barrier.wait()
            try:
                lease = keeper.grant("hot", "n%d" % index, 60.0)
                with lock:
                    outcomes.append(lease.token)
            except LeaseConflict:
                with lock:
                    outcomes.append(None)

        workers = [
            threading.Thread(target=contend, args=(i,))
            for i in range(contenders)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        winners = [token for token in outcomes if token is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(keeper.stats().grants, 1)
        self.assertEqual(keeper.stats().conflicts, contenders - 1)


if __name__ == "__main__":
    unittest.main()
