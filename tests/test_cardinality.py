"""基数控制行为：超限降级、按指标隔离、可观测、可恢复、导出限流。"""
import json
import unittest

from metrics import Registry
from metrics.registry import OVERFLOW_LABEL


def overflow_series(metric_snap):
    for s in metric_snap["series"]:
        if all(v == OVERFLOW_LABEL for v in s["labels"].values()):
            return s
    return None


class TestOverflowDegradation(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        self.c = self.reg.counter("http_requests", ["path", "user_id"], max_series=2)

    def test_over_limit_series_go_to_overflow_bucket(self):
        self.c.inc(path="/a", user_id="u1")
        self.c.inc(path="/b", user_id="u2")
        self.c.inc(3, path="/c", user_id="u3")
        snap = self.c.snapshot()
        real = [s for s in snap["series"] if s["labels"]["user_id"] != OVERFLOW_LABEL]
        self.assertEqual(len(real), 2)
        self.assertEqual(overflow_series(snap)["value"], 3)

    def test_metric_not_rejected_wholesale(self):
        self.c.inc(path="/a", user_id="u1")
        for i in range(100):
            self.c.inc(path="/x", user_id=f"u{i}")
        self.c.inc(5, path="/a", user_id="u1")
        self.assertEqual(self.c.value(path="/a", user_id="u1"), 6)
        self.assertEqual(overflow_series(self.c.snapshot())["value"], 99)

    def test_repeated_overflow_key_aggregates(self):
        self.c.inc(path="/a", user_id="u1")
        self.c.inc(path="/b", user_id="u2")
        for _ in range(4):
            self.c.inc(path="/c", user_id="u3")
        self.assertEqual(overflow_series(self.c.snapshot())["value"], 4)

    def test_gauge_overflow_keeps_last_value(self):
        g = self.reg.gauge("temp", ["room"], max_series=1)
        g.set(20, room="a")
        g.set(25, room="b")
        g.set(26, room="b")
        self.assertEqual(overflow_series(g.snapshot())["value"], 26)


class TestPerMetricIsolation(unittest.TestCase):
    def test_limits_are_per_metric(self):
        reg = Registry()
        a = reg.counter("a", ["id"], max_series=1)
        b = reg.counter("b", ["id"], max_series=10)
        a.inc(id="x")
        a.inc(id="y")
        b.inc(id="x")
        b.inc(id="y")
        self.assertIsNotNone(overflow_series(a.snapshot()))
        self.assertIsNone(overflow_series(b.snapshot()))
        self.assertEqual(b.value(id="y"), 1)

    def test_registry_default_limit_with_override(self):
        reg = Registry(max_series=2)
        a = reg.counter("a", ["id"])
        b = reg.counter("b", ["id"], max_series=5)
        self.assertEqual(a.max_series, 2)
        self.assertEqual(b.max_series, 5)

    def test_no_limit_keeps_unlimited_behavior(self):
        c = Registry().counter("c", ["id"])
        for i in range(1000):
            c.inc(id=f"u{i}")
        snap = c.snapshot()
        self.assertEqual(len(snap["series"]), 1000)
        self.assertNotIn("cardinality", snap)


class TestObservability(unittest.TestCase):
    def test_dropped_writes_and_keys_reported(self):
        c = Registry().counter("c", ["user_id"], max_series=1)
        c.inc(user_id="u1")
        c.inc(user_id="u2")
        c.inc(2, user_id="u2")
        c.inc(user_id="u3")
        card = c.snapshot()["cardinality"]
        self.assertEqual(card["limit"], 1)
        self.assertEqual(card["series"], 1)
        self.assertTrue(card["overflowed"])
        self.assertEqual(card["dropped_writes"], 3)
        dropped = {d["labels"]["user_id"]: d["writes"] for d in card["dropped_keys"]}
        self.assertEqual(dropped, {"u2": 2, "u3": 1})

    def test_snapshot_stays_json_serializable_when_limited(self):
        c = Registry().counter("c", ["user_id"], max_series=1)
        c.inc(user_id="u1")
        c.inc(user_id="u2")
        json.dumps(c.snapshot())


class TestRecovery(unittest.TestCase):
    def test_dropped_key_recovers_after_reset(self):
        c = Registry().counter("c", ["user_id"], max_series=1)
        c.inc(user_id="u1")
        c.inc(7, user_id="u2")
        c.reset()
        c.inc(user_id="u2")
        self.assertEqual(c.value(user_id="u2"), 1)
        snap = c.snapshot()
        self.assertEqual(overflow_series(snap)["value"], 7)
        recovered = {d["labels"]["user_id"] for d in snap["cardinality"]["dropped_keys"]}
        self.assertNotIn("u2", recovered)

    def test_reset_keeps_accounting_for_observability(self):
        c = Registry().counter("c", ["user_id"], max_series=1)
        c.inc(user_id="u1")
        c.inc(user_id="u2")
        c.reset()
        card = c.snapshot()["cardinality"]
        self.assertEqual(card["series"], 0)
        self.assertEqual(card["dropped_writes"], 1)


class TestExportBudget(unittest.TestCase):
    def test_series_budget_truncates_export(self):
        reg = Registry()
        a = reg.counter("a", ["id"])
        b = reg.counter("b", ["id"])
        for i in range(5):
            a.inc(id=f"x{i}")
            b.inc(id=f"y{i}")
        snap = reg.snapshot(series_budget=7)
        ma, mb = snap["metrics"]
        self.assertEqual(len(ma["series"]), 5)
        self.assertNotIn("truncated", ma)
        self.assertEqual(len(mb["series"]), 2)
        self.assertTrue(mb["truncated"])
        total = sum(len(m["series"]) for m in snap["metrics"])
        self.assertLessEqual(total, 7)

    def test_zero_budget_truncates_everything(self):
        reg = Registry()
        reg.counter("a", ["id"]).inc(id="x")
        snap = reg.snapshot(series_budget=0)
        self.assertEqual(snap["metrics"][0]["series"], [])
        self.assertTrue(snap["metrics"][0]["truncated"])

    def test_no_budget_exports_everything(self):
        reg = Registry()
        c = reg.counter("a", ["id"])
        for i in range(10):
            c.inc(id=f"x{i}")
        self.assertEqual(len(reg.snapshot()["metrics"][0]["series"]), 10)


if __name__ == "__main__":
    unittest.main()
