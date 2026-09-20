"""Registry 行为基线。"""
import json
import threading
import unittest

from metrics import Counter, DuplicateMetric, Gauge, Registry


class TestRegistration(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()

    def test_registers_counter_and_gauge(self):
        c = self.reg.counter("http_requests", ["path"])
        g = self.reg.gauge("queue_depth", ["queue"])
        self.assertIsInstance(c, Counter)
        self.assertIsInstance(g, Gauge)

    def test_get_returns_same_object(self):
        c = self.reg.counter("hits")
        self.assertIs(self.reg.get("hits"), c)

    def test_duplicate_name_rejected(self):
        self.reg.counter("hits")
        with self.assertRaises(DuplicateMetric):
            self.reg.counter("hits")
        with self.assertRaises(DuplicateMetric):
            self.reg.gauge("hits")

    def test_label_names_preserved_in_order(self):
        c = self.reg.counter("hits", ["b", "a"])
        self.assertEqual(c.label_names, ("b", "a"))


class TestCounter(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        self.c = self.reg.counter("http_requests", ["path", "status"])

    def test_inc_default_amount(self):
        self.c.inc(path="/", status="200")
        self.assertEqual(self.c.value(path="/", status="200"), 1)

    def test_inc_accumulates_per_series(self):
        for _ in range(3):
            self.c.inc(path="/", status="200")
        self.c.inc(path="/", status="500")
        self.assertEqual(self.c.value(path="/", status="200"), 3)
        self.assertEqual(self.c.value(path="/", status="500"), 1)

    def test_inc_with_amount(self):
        self.c.inc(5, path="/", status="200")
        self.assertEqual(self.c.value(path="/", status="200"), 5)

    def test_missing_label_is_empty_string(self):
        self.c.inc(path="/")
        self.assertEqual(self.c.value(path="/", status=""), 1)

    def test_unknown_series_value_is_zero(self):
        self.assertEqual(self.c.value(path="/nope", status="404"), 0)

    def test_concurrent_inc_is_accurate(self):
        c = self.reg.counter("conc", ["worker"])
        threads = [
            threading.Thread(target=lambda: [c.inc(worker="w") for _ in range(200)])
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(c.value(worker="w"), 1600)


class TestGauge(unittest.TestCase):
    def test_set_and_overwrite(self):
        g = Registry().gauge("queue_depth", ["queue"])
        g.set(3, queue="default")
        self.assertEqual(g.value(queue="default"), 3)
        g.set(0, queue="default")
        self.assertEqual(g.value(queue="default"), 0)

    def test_missing_gauge_is_none(self):
        g = Registry().gauge("queue_depth", ["queue"])
        self.assertIsNone(g.value(queue="nope"))


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        http = self.reg.counter("http_requests", ["path"])
        http.inc(2, path="/")
        http.inc(path="/api")
        self.reg.gauge("a_depth", ["q"]).set(7, q="default")

    def test_snapshot_shape(self):
        snap = self.reg.snapshot()
        self.assertEqual(list(snap), ["metrics"])
        self.assertEqual([m["name"] for m in snap["metrics"]], ["a_depth", "http_requests"])

    def test_snapshot_series_payload(self):
        snap = json.loads(json.dumps(self.reg.snapshot()))
        http = [m for m in snap["metrics"] if m["name"] == "http_requests"][0]
        self.assertEqual(http["type"], "counter")
        self.assertEqual(http["label_names"], ["path"])
        self.assertEqual(
            http["series"],
            [{"labels": {"path": "/"}, "value": 2}, {"labels": {"path": "/api"}, "value": 1}],
        )

    def test_snapshot_is_json_serializable(self):
        json.dumps(self.reg.snapshot())

    def test_snapshot_reflects_later_writes(self):
        self.reg.get("http_requests").inc(path="/")
        snap = self.reg.snapshot()
        http = [m for m in snap["metrics"] if m["name"] == "http_requests"][0]
        self.assertEqual([s["value"] for s in http["series"]], [3, 1])


if __name__ == "__main__":
    unittest.main()
