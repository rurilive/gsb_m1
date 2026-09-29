"""Aggregate 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：追加事件即重放、全量重放、事件流快照与版本号。
新增行为（快照增量重放、乐观并发、幂等重放、损坏回退、区间查询）另建测试文件，
不改动本文件。
"""

import unittest

from evokit.aggregate import Aggregate, Event, apply_default


class TestAppendAndReplay(unittest.TestCase):
    def test_append_returns_increasing_versions(self):
        agg = Aggregate()
        self.assertEqual(agg.append("created", {"field": "name", "value": "x"}), 1)
        self.assertEqual(agg.append("renamed", {"field": "name", "value": "y"}), 2)
        self.assertEqual(agg.version, 2)

    def test_state_follows_last_event(self):
        agg = Aggregate()
        agg.append("created", {"field": "name", "value": "x"})
        agg.append("renamed", {"field": "name", "value": "y"})
        self.assertEqual(agg.state, {"name": "y"})

    def test_replay_rebuilds_from_scratch(self):
        agg = Aggregate()
        agg.append("created", {"field": "name", "value": "x"})
        agg.append("renamed", {"field": "name", "value": "y"})
        self.assertEqual(agg.replay(), {"name": "y"})

    def test_replay_ignores_current_state(self):
        agg = Aggregate()
        agg.append("created", {"field": "n", "value": 1})
        agg._state = {"poison": True}  # 直接篡改，验证 replay 不依赖现状
        self.assertEqual(agg.replay(), {"n": 1})

    def test_event_without_field_leaves_state(self):
        agg = Aggregate()
        agg.append("created", {"field": "n", "value": 1})
        agg.append("logged", {"note": "nothing"})
        self.assertEqual(agg.state, {"n": 1})


class TestEventsSnapshot(unittest.TestCase):
    def test_events_are_copies(self):
        agg = Aggregate()
        agg.append("created", {"field": "n", "value": 1})
        snap = agg.events()
        snap[0].data["value"] = 999
        self.assertEqual(agg.events()[0].data["value"], 1)

    def test_events_are_version_ordered(self):
        agg = Aggregate()
        for i in range(4):
            agg.append("tick", {"field": "n", "value": i})
        versions = [e.version for e in agg.events()]
        self.assertEqual(versions, [1, 2, 3, 4])


class TestDefaultApply(unittest.TestCase):
    def test_apply_default_sets_field(self):
        state = apply_default(Event(1, "set", {"field": "a", "value": 5}), {})
        self.assertEqual(state, {"a": 5})

    def test_apply_default_without_field(self):
        state = {"a": 1}
        self.assertIs(apply_default(Event(1, "noop", {}), state), state)


class TestCustomApply(unittest.TestCase):
    def test_custom_apply_accumulates(self):
        def acc(event, state):
            return {"total": state.get("total", 0) + event.data.get("n", 0)}

        agg = Aggregate(apply=acc, initial={"total": 0})
        agg.append("add", {"n": 3})
        agg.append("add", {"n": 4})
        self.assertEqual(agg.state, {"total": 7})
        self.assertEqual(agg.replay(), {"total": 7})


if __name__ == "__main__":
    unittest.main()
