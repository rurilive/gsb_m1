"""静态成员表与整表广播的锁定测试：加入、查询、观察与合并。

只覆盖当前已支持的能力。心跳与失败探测、怀疑与死亡三态、版本化传播、
反熵与故障恢复另开测试文件。
"""

import unittest

from swimsim import DefinitionError, Node, UnknownMember, ManualClock
from swimsim.node import Node as NodeFromModule


def build(clock=None):
    """一个最小可用的三节点成员表。"""
    if clock is None:
        clock = ManualClock()
    return Node(name="n1", members=["n1", "n2", "n3"], clock=clock)


class TestConstruction(unittest.TestCase):
    def test_name_is_exposed(self):
        self.assertEqual(build().name, "n1")

    def test_known_members_are_sorted(self):
        self.assertEqual(build().known(), ("n1", "n2", "n3"))

    def test_empty_node_name_is_rejected(self):
        with self.assertRaises(DefinitionError):
            Node(name="")

    def test_non_string_node_name_is_rejected(self):
        with self.assertRaises(DefinitionError):
            Node(name=7)

    def test_duplicate_member_is_rejected(self):
        n = Node(name="n1", members=["n1"])
        with self.assertRaises(DefinitionError):
            n.add_member("n1")

    def test_empty_member_name_is_rejected(self):
        n = Node(name="n1")
        with self.assertRaises(DefinitionError):
            n.add_member("")

    def test_add_member_returns_self(self):
        n = Node(name="n1")
        self.assertIs(n.add_member("n2"), n)

    def test_exported_from_package_and_module(self):
        self.assertIs(Node, NodeFromModule)


class TestQueries(unittest.TestCase):
    def test_has(self):
        n = build()
        self.assertTrue(n.has("n2"))
        self.assertFalse(n.has("n9"))

    def test_record_returns_current_record(self):
        self.assertEqual(build().record("n2").name, "n2")

    def test_record_of_unknown_member_is_rejected(self):
        with self.assertRaises(UnknownMember):
            build().record("n9")

    def test_members_start_alive(self):
        n = build()
        self.assertTrue(n.is_alive("n1"))
        self.assertTrue(n.is_alive("n3"))

    def test_is_alive_of_unknown_member_is_rejected(self):
        with self.assertRaises(UnknownMember):
            build().is_alive("n9")

    def test_unknown_member_is_a_swim_error(self):
        from swimsim import SwimError
        with self.assertRaises(SwimError):
            build().record("n9")


class TestObserve(unittest.TestCase):
    def test_observe_stamps_clock_now(self):
        clock = ManualClock(start=5.0)
        n = build(clock)
        self.assertEqual(n.observe("n2", alive=True).last_seen, 5.0)

    def test_observe_can_mark_not_alive(self):
        n = build()
        n.observe("n2", alive=False)
        self.assertFalse(n.is_alive("n2"))

    def test_observe_does_not_touch_other_members(self):
        n = build()
        n.observe("n2", alive=False)
        self.assertTrue(n.is_alive("n3"))

    def test_observe_rejects_unknown_member(self):
        with self.assertRaises(UnknownMember):
            build().observe("n9")

    def test_seen_at_returns_new_record(self):
        original = build().record("n2")
        bumped = original.seen_at(9.0)
        self.assertEqual(bumped.last_seen, 9.0)
        self.assertIsNot(bumped, original)


class TestGossipBaseline(unittest.TestCase):
    def test_gossip_serializes_whole_table(self):
        snapshot = build().gossip("n2")
        self.assertEqual([e["name"] for e in snapshot], ["n1", "n2", "n3"])

    def test_gossip_entries_carry_no_version(self):
        entry = build().gossip("n1")[0]
        self.assertEqual(sorted(entry), ["alive", "last_seen", "name"])

    def test_gossip_rejects_unknown_source(self):
        with self.assertRaises(UnknownMember):
            build().gossip("n9")


class TestMergeBaseline(unittest.TestCase):
    def test_newer_snapshot_overwrites(self):
        n = build()
        n.merge([{"name": "n2", "alive": False, "last_seen": 99.0}])
        self.assertFalse(n.is_alive("n2"))

    def test_older_snapshot_is_ignored(self):
        clock = ManualClock(start=10.0)
        n = build(clock)
        n.observe("n2", alive=False)
        n.merge([{"name": "n2", "alive": True, "last_seen": 1.0}])
        self.assertFalse(n.is_alive("n2"))

    def test_equal_timestamp_keeps_local(self):
        clock = ManualClock(start=4.0)
        n = build(clock)
        n.observe("n2", alive=True)
        n.merge([{"name": "n2", "alive": False, "last_seen": 4.0}])
        self.assertTrue(n.is_alive("n2"))

    def test_merge_adds_unknown_member(self):
        n = build()
        n.merge([{"name": "n4", "alive": True, "last_seen": 1.0}])
        self.assertTrue(n.has("n4"))

    def test_bad_entry_is_rejected(self):
        with self.assertRaises(DefinitionError):
            build().merge([{"alive": True}])

    def test_bad_container_is_rejected(self):
        with self.assertRaises(DefinitionError):
            build().merge("nope")

    def test_merge_returns_self(self):
        n = build()
        self.assertIs(n.merge([]), n)


if __name__ == "__main__":
    unittest.main()