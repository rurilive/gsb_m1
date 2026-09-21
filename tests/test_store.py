"""CausalStore 现有行为的锁定测试。"""

import unittest

from causalsnap.store import CausalStore, Event


class TestRecordAndLocal(unittest.TestCase):
    def test_record_returns_increasing_seq(self):
        store = CausalStore()
        self.assertEqual(store.record("alice", "login"), 0)
        self.assertEqual(store.record("alice", "edit"), 1)
        self.assertEqual(store.record("alice", "logout"), 2)

    def test_seq_is_per_process(self):
        store = CausalStore()
        store.record("alice", "login")
        store.record("alice", "edit")
        self.assertEqual(store.record("bob", "join"), 0)
        self.assertEqual(store.record("bob", "leave"), 1)

    def test_local_returns_events_in_order(self):
        store = CausalStore()
        store.record("alice", "login")
        store.record("alice", "edit")
        events = store.local("alice")
        self.assertEqual([e.payload for e in events], ["login", "edit"])
        self.assertEqual([e.seq for e in events], [0, 1])
        self.assertTrue(all(e.proc == "alice" for e in events))

    def test_local_unknown_process_is_empty(self):
        store = CausalStore()
        self.assertEqual(store.local("nobody"), ())

    def test_local_returns_fresh_tuple(self):
        store = CausalStore()
        store.record("alice", "login")
        first = store.local("alice")
        store.record("alice", "edit")
        self.assertEqual(len(first), 1)
        self.assertEqual(len(store.local("alice")), 2)

    def test_last(self):
        store = CausalStore()
        self.assertIsNone(store.last("alice"))
        store.record("alice", "login")
        store.record("alice", "edit")
        self.assertEqual(store.last("alice").payload, "edit")

    def test_processes_sorted(self):
        store = CausalStore()
        store.record("carol", "x")
        store.record("alice", "y")
        store.record("bob", "z")
        self.assertEqual(store.processes(), ("alice", "bob", "carol"))

    def test_clock_is_injectable(self):
        ticks = iter([10.0, 20.0, 30.0])
        store = CausalStore(clock=lambda: next(ticks))
        store.record("alice", "a")
        store.record("alice", "b")
        store.record("bob", "c")
        self.assertEqual([e.at for e in store.local("alice")], [10.0, 20.0])
        self.assertEqual(store.last("bob").at, 30.0)


class TestSharedCells(unittest.TestCase):
    def test_publish_then_fetch(self):
        store = CausalStore()
        store.publish("alice", "doc", "draft")
        self.assertEqual(store.fetch("doc"), "draft")

    def test_fetch_missing_returns_default(self):
        store = CausalStore()
        self.assertIsNone(store.fetch("nope"))
        self.assertEqual(store.fetch("nope", 0), 0)

    def test_publish_overwrites_and_lists_cells(self):
        store = CausalStore()
        store.publish("alice", "doc", "draft")
        store.publish("bob", "doc", "final")
        store.publish("bob", "lock", "held")
        self.assertEqual(store.fetch("doc"), "final")
        self.assertEqual(store.cells(), ("doc", "lock"))


class TestEvent(unittest.TestCase):
    def test_identity_is_process_and_seq(self):
        a = Event("alice", 0, "login", 1.0)
        b = Event("alice", 0, "something else", 9.0)
        c = Event("bob", 0, "login", 1.0)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len({a, b, c}), 2)

    def test_repr_mentions_process_and_seq(self):
        text = repr(Event("alice", 3, "login", 1.0))
        self.assertIn("alice", text)
        self.assertIn("3", text)


if __name__ == "__main__":
    unittest.main()
