"""因果序与一致性快照的测试。"""

import unittest

from causalsnap.store import CausalStore, compare


class TestVectorClock(unittest.TestCase):
    def test_event_carries_vector_clock(self):
        store = CausalStore()
        store.record("alice", "a")
        store.record("alice", "b")
        first, second = store.local("alice")
        self.assertEqual(first.vclock, {"alice": 1})
        self.assertEqual(second.vclock, {"alice": 2})

    def test_independent_events_are_concurrent(self):
        store = CausalStore()
        store.record("alice", "a")
        store.record("bob", "b")
        alice_event = store.last("alice")
        bob_event = store.last("bob")
        self.assertEqual(compare(alice_event, bob_event), "concurrent")
        self.assertEqual(compare(bob_event, alice_event), "concurrent")

    def test_same_process_events_are_ordered(self):
        store = CausalStore()
        store.record("alice", "a")
        store.record("alice", "b")
        first, second = store.local("alice")
        self.assertEqual(compare(first, second), "before")
        self.assertEqual(compare(second, first), "after")

    def test_same_event_is_equal(self):
        store = CausalStore()
        store.record("alice", "a")
        event = store.last("alice")
        self.assertEqual(compare(event, event), "equal")


class TestObserve(unittest.TestCase):
    def test_observe_establishes_order(self):
        store = CausalStore()
        store.record("alice", "a")
        store.observe("bob", "alice", 0)
        store.record("bob", "b")
        alice_event = store.last("alice")
        bob_event = store.last("bob")
        self.assertEqual(compare(alice_event, bob_event), "before")
        self.assertEqual(compare(bob_event, alice_event), "after")

    def test_observe_merges_transitively(self):
        store = CausalStore()
        store.record("alice", "a")
        store.observe("bob", "alice", 0)
        store.record("bob", "b")
        store.observe("carol", "bob", 0)
        snap = store.snapshot("carol")
        self.assertEqual(snap.cut, {"alice": 1, "bob": 1})

    def test_unobserved_direction_stays_concurrent(self):
        store = CausalStore()
        store.record("alice", "a")
        store.record("bob", "b")
        store.observe("bob", "alice", 0)
        # alice 从未见过 bob 的事件，两边互不知情
        self.assertEqual(compare(store.last("alice"), store.last("bob")), "concurrent")

    def test_observe_unknown_event_raises(self):
        store = CausalStore()
        with self.assertRaises(IndexError):
            store.observe("bob", "alice", 0)


class TestSnapshot(unittest.TestCase):
    def _store(self):
        store = CausalStore()
        store.record("alice", "a0")
        store.record("alice", "a1")
        store.record("bob", "b0")
        store.observe("bob", "alice", 0)
        store.record("bob", "b1")
        return store

    def test_cut_and_grouped_events(self):
        snap = self._store().snapshot("bob")
        self.assertEqual(snap.observer, "bob")
        self.assertEqual(snap.cut, {"alice": 1, "bob": 2})
        self.assertEqual([e.payload for e in snap.events["alice"]], ["a0"])
        self.assertEqual([e.payload for e in snap.events["bob"]], ["b0", "b1"])

    def test_snapshot_only_contains_known_events(self):
        snap = self._store().snapshot("alice")
        self.assertEqual(snap.cut, {"alice": 2})
        self.assertNotIn("bob", snap.events)

    def test_unknown_observer_gets_empty_snapshot(self):
        snap = CausalStore().snapshot("nobody")
        self.assertEqual(snap.cut, {})
        self.assertEqual(snap.events, {})

    def test_snapshot_is_stable_after_new_events(self):
        store = self._store()
        snap = store.snapshot("bob")
        store.record("bob", "b2")
        store.observe("bob", "alice", 1)
        self.assertEqual(snap.cut, {"alice": 1, "bob": 2})
        self.assertEqual(len(snap.events["bob"]), 2)

    def test_newer_and_older(self):
        store = self._store()
        older = store.snapshot("bob")
        store.observe("bob", "alice", 1)
        store.record("bob", "b2")
        newer = store.snapshot("bob")
        self.assertEqual(newer.compare(older), "newer")
        self.assertEqual(older.compare(newer), "older")

    def test_equal_snapshots(self):
        store = self._store()
        self.assertEqual(store.snapshot("bob").compare(store.snapshot("bob")), "equal")

    def test_concurrent_snapshots_are_not_forced(self):
        store = self._store()
        alice_view = store.snapshot("alice")
        bob_view = store.snapshot("bob")
        self.assertEqual(alice_view.compare(bob_view), "concurrent")
        self.assertEqual(bob_view.compare(alice_view), "concurrent")


if __name__ == "__main__":
    unittest.main()
