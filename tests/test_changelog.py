"""ChangeLog 现有行为的锁定测试。"""

import unittest

from changelogd.changelog import Change, ChangeLog


class TestAppendAndHistory(unittest.TestCase):
    def test_append_returns_record(self):
        log = ChangeLog()
        c = log.append("u1", "title", "hello", 1)
        self.assertEqual(c.obj, "u1")
        self.assertEqual(c.field, "title")
        self.assertEqual(c.value, "hello")
        self.assertEqual(c.version, 1)

    def test_history_keeps_append_order(self):
        log = ChangeLog()
        log.append("u1", "b", 2, 1)
        log.append("u1", "a", 1, 2)
        self.assertEqual([c.field for c in log.history("u1")], ["b", "a"])

    def test_history_unknown_object_is_empty(self):
        self.assertEqual(ChangeLog().history("nope"), [])

    def test_history_returns_fresh_list(self):
        log = ChangeLog()
        log.append("u1", "a", 1, 1)
        h = log.history("u1")
        h.clear()
        self.assertEqual(len(log.history("u1")), 1)

    def test_objects_in_first_seen_order(self):
        log = ChangeLog()
        log.append("u1", "a", 1, 1)
        log.append("u2", "a", 1, 1)
        log.append("u1", "b", 2, 2)
        self.assertEqual(log.objects(), ["u1", "u2"])


class TestAt(unittest.TestCase):
    def test_at_uses_only_changes_up_to_version(self):
        log = ChangeLog()
        log.append("u1", "title", "v1", 1)
        log.append("u1", "title", "v2", 3)
        self.assertEqual(log.at("u1", 2), {"title": "v1"})
        self.assertEqual(log.at("u1", 3), {"title": "v2"})

    def test_at_version_boundary_is_inclusive(self):
        log = ChangeLog()
        log.append("u1", "a", 1, 5)
        self.assertEqual(log.at("u1", 4), {})
        self.assertEqual(log.at("u1", 5), {"a": 1})

    def test_at_latest_change_per_field_wins(self):
        log = ChangeLog()
        log.append("u1", "a", 1, 1)
        log.append("u1", "b", 2, 1)
        log.append("u1", "a", 3, 2)
        self.assertEqual(log.at("u1", 2), {"a": 3, "b": 2})

    def test_at_ties_broken_by_append_order(self):
        # 同一版本上重复写同一字段，以 append 顺序在后的为准
        log = ChangeLog()
        log.append("u1", "a", "first", 1)
        log.append("u1", "a", "second", 1)
        self.assertEqual(log.at("u1", 1), {"a": "second"})

    def test_at_unknown_object_is_empty(self):
        self.assertEqual(ChangeLog().at("nope", 99), {})

    def test_at_returns_fresh_dict(self):
        log = ChangeLog()
        log.append("u1", "a", 1, 1)
        snap = log.at("u1", 1)
        snap["a"] = 99
        self.assertEqual(log.at("u1", 1), {"a": 1})

    def test_objects_are_independent(self):
        log = ChangeLog()
        log.append("u1", "a", 1, 1)
        log.append("u2", "a", 2, 1)
        self.assertEqual(log.at("u1", 1), {"a": 1})
        self.assertEqual(log.at("u2", 1), {"a": 2})


class TestClock(unittest.TestCase):
    def test_clock_is_injectable(self):
        log = ChangeLog(clock=lambda: 123.0)
        self.assertEqual(log.append("u1", "a", 1, 1).ts, 123.0)

    def test_clock_called_once_per_append(self):
        ticks = iter([10.0, 20.0])
        log = ChangeLog(clock=lambda: next(ticks))
        log.append("u1", "a", 1, 1)
        log.append("u1", "b", 2, 2)
        self.assertEqual([c.ts for c in log.history("u1")], [10.0, 20.0])

    def test_change_exposes_core_fields(self):
        log = ChangeLog()
        change = log.append("u1", "a", 1, 1)
        self.assertIsInstance(change, Change)
        for name in ("obj", "field", "value", "version", "ts"):
            self.assertTrue(hasattr(change, name))


if __name__ == "__main__":
    unittest.main()
