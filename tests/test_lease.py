"""LeaseManager 现有行为的锁定测试。"""

import unittest

from batchlease.lease import (
    LeaseManager,
    MemberTable,
    NoLease,
    UnknownMember,
)


class FakeClock:
    """手动推进的假时钟。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


def make_manager(members=None, start=0.0):
    clock = FakeClock(start)
    mgr = LeaseManager(members, clock=clock)
    return mgr, clock


class TestMemberTable(unittest.TestCase):
    def test_initial_members_stay_generation_zero(self):
        table = MemberTable({"a": 1, "b": 2})
        self.assertEqual(table.generation(), 0)
        self.assertEqual(table.nodes(), ["a", "b"])

    def test_add_bumps_generation(self):
        table = MemberTable()
        self.assertTrue(table.add("a", 1))
        self.assertEqual(table.generation(), 1)

    def test_add_same_priority_is_noop(self):
        table = MemberTable({"a": 1})
        self.assertFalse(table.add("a", 1))
        self.assertEqual(table.generation(), 0)

    def test_remove_bumps_only_when_present(self):
        table = MemberTable({"a": 1})
        self.assertTrue(table.remove("a"))
        self.assertEqual(table.generation(), 1)
        self.assertFalse(table.remove("a"))
        self.assertEqual(table.generation(), 1)

    def test_priority_of_stranger_raises(self):
        with self.assertRaises(UnknownMember):
            MemberTable().priority("ghost")

    def test_contains_and_len(self):
        table = MemberTable({"a": 1})
        self.assertIn("a", table)
        self.assertNotIn("b", table)
        self.assertEqual(len(table), 1)


class TestElection(unittest.TestCase):
    def test_primary_is_highest_priority(self):
        mgr, _ = make_manager({"a": 1, "b": 5, "c": 3})
        self.assertEqual(mgr.primary(), "b")

    def test_primary_tie_breaks_by_name(self):
        mgr, _ = make_manager({"zeta": 2, "alpha": 2})
        self.assertEqual(mgr.primary(), "alpha")

    def test_primary_of_empty_table_is_none(self):
        mgr, _ = make_manager({})
        self.assertIsNone(mgr.primary())

    def test_primary_follows_table_edits(self):
        mgr, _ = make_manager({"a": 1})
        self.assertEqual(mgr.primary(), "a")
        mgr.table.add("b", 9)
        self.assertEqual(mgr.primary(), "b")


class TestAcquire(unittest.TestCase):
    def test_acquire_returns_expiry_from_clock(self):
        mgr, clock = make_manager({"a": 0}, start=100.0)
        self.assertEqual(mgr.acquire("a", ttl=10.0), 110.0)

    def test_acquire_uses_default_ttl(self):
        mgr, _ = make_manager({"a": 0})
        self.assertEqual(mgr.acquire("a"), 30.0)

    def test_acquire_unknown_member_raises(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(UnknownMember):
            mgr.acquire("ghost", ttl=1.0)

    def test_acquire_rejects_non_positive_ttl(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(ValueError):
            mgr.acquire("a", ttl=0)
        with self.assertRaises(ValueError):
            mgr.acquire("a", ttl=-1)

    def test_repeated_acquire_appends_segments(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(4.0)
        mgr.acquire("a", ttl=10.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 10.0), (4.0, 14.0)])

    def test_expires_at_is_latest_segment_end(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(1.0)
        mgr.acquire("a", ttl=2.0)
        self.assertEqual(mgr.expires_at("a"), 10.0)

    def test_expires_at_without_lease_is_none(self):
        mgr, _ = make_manager({"a": 0})
        self.assertIsNone(mgr.expires_at("a"))

    def test_segments_returns_copy(self):
        mgr, _ = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        snapshot = mgr.segments("a")
        snapshot.append((99.0, 100.0))
        self.assertEqual(mgr.segments("a"), [(0.0, 10.0)])


class TestRenew(unittest.TestCase):
    def test_renew_pushes_last_segment_end(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(5.0)
        self.assertEqual(mgr.renew("a"), 35.0)
        self.assertEqual(mgr.expires_at("a"), 35.0)

    def test_renew_only_touches_last_segment(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(3.0)
        mgr.acquire("a", ttl=10.0)
        clock.advance(1.0)
        mgr.renew("a")
        self.assertEqual(mgr.segments("a"), [(0.0, 10.0), (3.0, 34.0)])

    def test_renew_without_acquire_raises(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(NoLease):
            mgr.renew("a")

    def test_renew_after_expiry_raises(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        clock.advance(5.0)
        with self.assertRaises(NoLease):
            mgr.renew("a")

    def test_renew_unknown_member_raises(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(UnknownMember):
            mgr.renew("ghost")


class TestReleaseAndHeld(unittest.TestCase):
    def test_release_reports_whether_held(self):
        mgr, _ = make_manager({"a": 0})
        self.assertFalse(mgr.release("a"))
        mgr.acquire("a", ttl=10.0)
        self.assertTrue(mgr.release("a"))

    def test_release_clears_every_segment(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(1.0)
        mgr.acquire("a", ttl=10.0)
        mgr.release("a")
        self.assertEqual(mgr.segments("a"), [])
        self.assertIsNone(mgr.expires_at("a"))

    def test_release_unknown_member_raises(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(UnknownMember):
            mgr.release("ghost")

    def test_held_follows_the_clock(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        self.assertTrue(mgr.held("a"))
        clock.advance(5.0)
        self.assertFalse(mgr.held("a"))

    def test_held_is_not_affected_by_other_nodes(self):
        mgr, clock = make_manager({"a": 0, "b": 0})
        mgr.acquire("a", ttl=5.0)
        mgr.acquire("b", ttl=1.0)
        clock.advance(2.0)
        self.assertTrue(mgr.held("a"))
        self.assertFalse(mgr.held("b"))


if __name__ == "__main__":
    unittest.main()
