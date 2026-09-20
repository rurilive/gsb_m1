"""批量申请、段落合并与批量释放的行为测试。"""

import unittest

from batchlease.lease import (
    LeaseManager,
    MembershipChanged,
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


class HookingClock:
    """读钟瞬间执行一次回调，用来模拟申请途中成员表变动。"""

    def __init__(self, inner, hook):
        self._inner = inner
        self._hook = hook

    def __call__(self):
        if self._hook is not None:
            hook, self._hook = self._hook, None
            hook()
        return self._inner()


def make_manager(members=None, start=0.0):
    clock = FakeClock(start)
    return LeaseManager(members, clock=clock), clock


class TestAcquireBatch(unittest.TestCase):
    def test_grants_one_segment_to_every_node_at_same_now(self):
        mgr, clock = make_manager({"a": 0, "b": 0, "c": 0})
        result = mgr.acquire_batch(["a", "b", "c"], ttl=10.0)
        self.assertEqual(result, {"a": 10.0, "b": 10.0, "c": 10.0})
        clock.advance(3.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 10.0)])
        self.assertEqual(mgr.segments("b"), [(0.0, 10.0)])
        self.assertTrue(mgr.held("c"))

    def test_unknown_member_aborts_whole_batch(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        with self.assertRaises(UnknownMember):
            mgr.acquire_batch(["a", "ghost", "b"], ttl=5.0)
        self.assertEqual(mgr.segments("a"), [])
        self.assertEqual(mgr.segments("b"), [])
        self.assertIsNone(mgr.expires_at("a"))

    def test_non_positive_ttl_rejected_without_touching_state(self):
        mgr, _ = make_manager({"a": 0})
        mgr.acquire("a", ttl=3.0)
        with self.assertRaises(ValueError):
            mgr.acquire_batch(["a"], ttl=0)
        with self.assertRaises(ValueError):
            mgr.acquire_batch(["a"], ttl=-2.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 3.0)])

    def test_duplicate_nodes_rejected(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(ValueError):
            mgr.acquire_batch(["a", "a"], ttl=5.0)
        self.assertEqual(mgr.segments("a"), [])

    def test_failure_does_not_roll_back_previously_held_segments(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        mgr.acquire("a", ttl=10.0)
        with self.assertRaises(UnknownMember):
            mgr.acquire_batch(["a", "ghost"], ttl=5.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 10.0)])

    def test_batch_does_not_merge_with_existing_segments(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(2.0)
        mgr.acquire_batch(["a"], ttl=10.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 10.0), (2.0, 12.0)])


class TestAcquireBatchMembershipChanges(unittest.TestCase):
    def test_member_added_during_batch_aborts_everything(self):
        clock = FakeClock()
        mgr = LeaseManager({"a": 0, "b": 0}, clock=HookingClock(
            clock, lambda: mgr.table.add("late", 0)))
        with self.assertRaises(MembershipChanged):
            mgr.acquire_batch(["a", "b"], ttl=10.0)
        self.assertEqual(mgr.segments("a"), [])
        self.assertEqual(mgr.segments("b"), [])
        self.assertIn("late", mgr.table.nodes())

    def test_member_removed_during_batch_aborts_everything(self):
        clock = FakeClock()
        mgr = LeaseManager({"a": 0, "b": 0}, clock=HookingClock(
            clock, lambda: mgr.table.remove("a")))
        with self.assertRaises(MembershipChanged):
            mgr.acquire_batch(["a", "b"], ttl=10.0)
        self.assertEqual(mgr.segments("b"), [])
        self.assertNotIn("a", mgr.table)
        mgr.table.add("a", 0)
        self.assertEqual(mgr.segments("a"), [])

    def test_generation_settled_before_call_lets_batch_proceed(self):
        mgr, clock = make_manager({"a": 0})
        mgr.table.add("b", 0)
        clock.advance(5.0)
        self.assertEqual(
            mgr.acquire_batch(["a", "b"], ttl=10.0),
            {"a": 15.0, "b": 15.0},
        )


class TestMerge(unittest.TestCase):
    def test_overlapping_segments_become_one_with_latest_end(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(4.0)
        mgr.acquire("a", ttl=10.0)
        self.assertEqual(mgr.merge("a"), [(0.0, 14.0)])

    def test_touching_segments_merge(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        clock.advance(5.0)
        mgr.acquire("a", ttl=5.0)
        self.assertEqual(mgr.merge("a"), [(0.0, 10.0)])

    def test_segments_with_gap_stay_apart(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        clock.advance(6.0)
        mgr.acquire("a", ttl=5.0)
        self.assertEqual(mgr.merge("a"), [(0.0, 5.0), (6.0, 11.0)])

    def test_contained_segment_keeps_outer_end(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(2.0)
        mgr.acquire("a", ttl=2.0)
        self.assertEqual(mgr.merge("a"), [(0.0, 10.0)])

    def test_merge_sorts_by_start_and_handles_multiple_groups(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)   # (0, 10)
        clock.advance(20.0)
        mgr.acquire("a", ttl=5.0)    # (20, 25)
        clock.advance(2.0)
        mgr.acquire("a", ttl=5.0)    # (22, 27) -> 并入第二组
        clock.advance(-20.0)
        mgr.acquire("a", ttl=3.0)    # (2, 5) -> 并入第一组
        self.assertEqual(
            mgr.merge("a"),
            [(0.0, 10.0), (20.0, 27.0)],
        )

    def test_merge_never_extends_expiry(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=10.0)
        clock.advance(5.0)
        mgr.acquire("a", ttl=2.0)    # (5, 7) 被 (0, 10) 包住
        clock.advance(6.0)
        mgr.merge("a")
        self.assertEqual(mgr.expires_at("a"), 10.0)

    def test_merge_empty_node_is_noop(self):
        mgr, _ = make_manager({"a": 0})
        self.assertEqual(mgr.merge("a"), [])
        self.assertEqual(mgr.segments("a"), [])

    def test_merge_unknown_member_raises(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(UnknownMember):
            mgr.merge("ghost")


class TestReleaseBatch(unittest.TestCase):
    def test_reports_released_empty_and_unknown(self):
        mgr, _ = make_manager({"a": 0, "b": 0, "c": 0})
        mgr.acquire("a", ttl=5.0)
        mgr.acquire("c", ttl=5.0)
        result = mgr.release_batch(["a", "b", "ghost", "c"])
        self.assertEqual(result.released, ["a", "c"])
        self.assertEqual(result.empty, ["b"])
        self.assertEqual(result.unknown, ["ghost"])
        for node in ("a", "b", "c"):
            self.assertEqual(mgr.segments(node), [])

    def test_later_failure_does_not_roll_back_earlier_release(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        mgr.acquire("a", ttl=5.0)
        mgr.acquire("b", ttl=5.0)
        result = mgr.release_batch(["a", "ghost", "b"])
        self.assertEqual(result.released, ["a", "b"])
        self.assertEqual(result.unknown, ["ghost"])
        self.assertFalse(mgr.held("a"))
        self.assertFalse(mgr.held("b"))

    def test_already_empty_nodes_count_as_empty_not_failure(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        mgr.acquire("a", ttl=5.0)
        mgr.release("a")
        result = mgr.release_batch(["a", "b"])
        self.assertEqual(result.released, [])
        self.assertEqual(result.empty, ["a", "b"])
        self.assertEqual(result.unknown, [])

    def test_duplicate_node_is_reported_once(self):
        mgr, _ = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        result = mgr.release_batch(["a", "a"])
        self.assertEqual(result.released, ["a"])
        self.assertEqual(result.empty, [])

        mgr.acquire("a", ttl=5.0)
        mgr.release("a")
        result = mgr.release_batch(["a", "a"])
        self.assertEqual(result.empty, ["a"])

    def test_empty_batch(self):
        mgr, _ = make_manager({"a": 0})
        result = mgr.release_batch([])
        self.assertEqual((result.released, result.empty, result.unknown),
                         ([], [], []))


if __name__ == "__main__":
    unittest.main()
