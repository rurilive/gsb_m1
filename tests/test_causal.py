"""向量时钟、因果比较与一致性快照的新行为测试。"""

import unittest

from causalsnap.store import CausalStore, Snapshot


class TestCompareEvents(unittest.TestCase):
    def test_same_event_is_equal(self):
        store = CausalStore()
        store.record("alice", "login")
        event = store.last("alice")
        self.assertEqual(store.compare(event, event), "equal")

    def test_local_order_is_before_after(self):
        store = CausalStore()
        store.record("alice", "a")
        store.record("alice", "b")
        first, second = store.local("alice")
        self.assertEqual(store.compare(first, second), "before")
        self.assertEqual(store.compare(second, first), "after")

    def test_unobserved_events_are_concurrent(self):
        store = CausalStore()
        store.record("alice", "a")
        store.record("bob", "b")
        self.assertEqual(store.compare(store.last("alice"), store.last("bob")), "concurrent")
        self.assertEqual(store.compare(store.last("bob"), store.last("alice")), "concurrent")

    def test_observe_establishes_order(self):
        store = CausalStore()
        store.record("alice", "a0")
        store.record("alice", "a1")
        store.observe("bob", "alice", 1)
        store.record("bob", "b0")
        a1 = store.local("alice")[1]
        b0 = store.last("bob")
        self.assertEqual(store.compare(a1, b0), "before")
        self.assertEqual(store.compare(b0, a1), "after")

    def test_observe_only_covers_up_to_seq(self):
        # bob 只收到 alice 的第 0 条，alice 后来的第 1 条与 bob 的新事件并发
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        store.record("alice", "a1")
        store.record("bob", "b0")
        self.assertEqual(store.compare(store.last("alice"), store.last("bob")), "concurrent")

    def test_observe_is_transitive(self):
        # carol 收到 bob 的事件，间接排在 alice 更早的事件之后
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        store.record("bob", "b0")
        store.observe("carol", "bob", 0)
        store.record("carol", "c0")
        self.assertEqual(store.compare(store.last("alice"), store.last("carol")), "before")

    def test_recorded_event_carries_vector_clock(self):
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        store.record("bob", "b0")
        self.assertEqual(store.last("bob").clock, {"alice": 0, "bob": 0})

    def test_observe_unknown_event_raises(self):
        store = CausalStore()
        with self.assertRaises(ValueError):
            store.observe("bob", "alice", 0)
        store.record("alice", "a0")
        with self.assertRaises(ValueError):
            store.observe("bob", "alice", 5)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_contains_only_known_events(self):
        store = CausalStore()
        store.record("alice", "a0")
        store.record("alice", "a1")
        store.observe("bob", "alice", 1)
        store.record("bob", "b0")
        store.record("carol", "c0")
        snap = store.snapshot("bob")
        self.assertEqual(snap.observer, "bob")
        self.assertEqual(snap.cut, {"alice": 1, "bob": 0})
        self.assertEqual([e.payload for e in snap.events["alice"]], ["a0", "a1"])
        self.assertEqual([e.payload for e in snap.events["bob"]], ["b0"])
        self.assertNotIn("carol", snap.events)

    def test_snapshot_cut_stops_at_observed_seq(self):
        # bob 只收到 alice 的第 0 条，快照不含 alice 后来的事件
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        store.record("alice", "a1")
        snap = store.snapshot("bob")
        self.assertEqual(snap.cut, {"alice": 0})
        self.assertEqual([e.payload for e in snap.events["alice"]], ["a0"])

    def test_snapshot_is_closed_under_causality(self):
        # carol 通过 bob 间接知道 alice：快照闭合，没有半截依赖
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        store.record("bob", "b0")
        store.record("carol", "c0")
        store.observe("carol", "bob", 0)
        snap = store.snapshot("carol")
        self.assertEqual(snap.cut, {"alice": 0, "bob": 0, "carol": 0})
        for group in snap.events.values():
            for event in group:
                for dep, upto in event.clock.items():
                    self.assertIn(dep, snap.cut)
                    self.assertGreaterEqual(snap.cut[dep], upto)

    def test_snapshot_of_unknown_observer_is_empty(self):
        store = CausalStore()
        store.record("alice", "a0")
        snap = store.snapshot("nobody")
        self.assertEqual(snap.cut, {})
        self.assertEqual(snap.events, {})

    def test_snapshot_compare_newer_older_equal(self):
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        first = store.snapshot("bob")
        store.record("alice", "a1")
        store.observe("bob", "alice", 1)
        store.record("bob", "b0")
        second = store.snapshot("bob")
        self.assertEqual(second.compare(first), "newer")
        self.assertEqual(first.compare(second), "older")
        self.assertEqual(first.compare(first), "equal")

    def test_snapshot_compare_concurrent_not_forced(self):
        store = CausalStore()
        store.record("alice", "a0")
        store.record("bob", "b0")
        snap_a = store.snapshot("alice")
        snap_b = store.snapshot("bob")
        self.assertEqual(snap_a.compare(snap_b), "concurrent")
        self.assertEqual(snap_b.compare(snap_a), "concurrent")

    def test_snapshot_compare_concurrent_with_shared_prefix(self):
        # 共同知道 alice 的第 0 条，之后各看各的，仍为并发
        store = CausalStore()
        store.record("alice", "a0")
        store.observe("bob", "alice", 0)
        store.observe("carol", "alice", 0)
        store.record("bob", "b0")
        store.record("carol", "c0")
        snap_b = store.snapshot("bob")
        snap_c = store.snapshot("carol")
        self.assertEqual(snap_b.compare(snap_c), "concurrent")

    def test_snapshot_repr_mentions_observer(self):
        snap = Snapshot("bob", {"alice": 1}, {})
        self.assertIn("bob", repr(snap))


if __name__ == "__main__":
    unittest.main()
