"""基数上限与溢出降级行为。"""
import json
import threading
import unittest

from metrics import DEFAULT_MAX_SERIES, OVERFLOW_LABEL, Registry


def overflow_series(metric_snap):
    return [s for s in metric_snap["series"] if OVERFLOW_LABEL in s["labels"].values()]


def real_series(metric_snap):
    return [s for s in metric_snap["series"] if OVERFLOW_LABEL not in s["labels"].values()]


class TestLimitEnforcement(unittest.TestCase):
    def test_under_limit_behaves_normally(self):
        c = Registry().counter("hits", ["path"], max_series=5)
        for i in range(5):
            c.inc(path=f"/p{i}")
        self.assertEqual(c.value(path="/p4"), 1)
        snap = c.snapshot()
        self.assertEqual(len(snap["series"]), 5)
        self.assertEqual(snap["cardinality"]["dropped_writes"], 0)

    def test_overflow_goes_to_fallback_bucket(self):
        c = Registry().counter("hits", ["path"], max_series=2)
        c.inc(path="/a")
        c.inc(path="/b")
        c.inc(3, path="/c")
        c.inc(2, path="/d")
        c.inc(4, path="/c")
        snap = c.snapshot()
        self.assertEqual(len(real_series(snap)), 2)
        bucket = overflow_series(snap)
        self.assertEqual(len(bucket), 1)
        self.assertEqual(bucket[0]["labels"], {"path": OVERFLOW_LABEL})
        self.assertEqual(bucket[0]["value"], 9)

    def test_existing_series_still_update_when_full(self):
        c = Registry().counter("hits", ["path"], max_series=1)
        c.inc(path="/a")
        c.inc(path="/b")
        c.inc(5, path="/a")
        self.assertEqual(c.value(path="/a"), 6)

    def test_dropped_series_value_reads_as_zero(self):
        c = Registry().counter("hits", ["path"], max_series=1)
        c.inc(path="/a")
        c.inc(path="/b")
        self.assertEqual(c.value(path="/b"), 0)

    def test_gauge_overflow_uses_last_write(self):
        g = Registry().gauge("depth", ["queue"], max_series=1)
        g.set(1, queue="q1")
        g.set(7, queue="q2")
        g.set(9, queue="q3")
        snap = g.snapshot()
        self.assertEqual(overflow_series(snap)[0]["value"], 9)
        self.assertIsNone(g.value(queue="q2"))

    def test_no_overflow_bucket_when_not_needed(self):
        c = Registry().counter("hits", ["path"], max_series=2)
        c.inc(path="/a")
        self.assertEqual(overflow_series(c.snapshot()), [])

    def test_invalid_max_series_rejected(self):
        with self.assertRaises(ValueError):
            Registry().counter("hits", max_series=0)


class TestPerMetricIsolation(unittest.TestCase):
    def test_limit_is_per_metric(self):
        reg = Registry(max_series=2)
        hot = reg.counter("hot", ["uid"])
        cold = reg.counter("cold", ["uid"])
        hot.inc(uid="u1")
        hot.inc(uid="u2")
        hot.inc(uid="u3")
        cold.inc(uid="u1")
        cold.inc(uid="u2")
        self.assertEqual(cold.value(uid="u2"), 1)
        self.assertEqual(overflow_series(hot.snapshot())[0]["value"], 1)

    def test_per_metric_override_beats_registry_default(self):
        reg = Registry(max_series=100)
        c = reg.counter("hits", ["uid"], max_series=1)
        c.inc(uid="u1")
        c.inc(uid="u2")
        self.assertEqual(c.snapshot()["cardinality"]["max_series"], 1)
        self.assertEqual(overflow_series(c.snapshot())[0]["value"], 1)

    def test_registry_default_limit_applies(self):
        c = Registry(max_series=7).counter("hits")
        self.assertEqual(c.max_series, 7)
        self.assertEqual(Registry().counter("hits").max_series, DEFAULT_MAX_SERIES)


class TestObservability(unittest.TestCase):
    def setUp(self):
        self.c = Registry().counter("hits", ["uid"], max_series=1)
        self.c.inc(uid="u1")
        self.c.inc(uid="u2")
        self.c.inc(2, uid="u3")
        self.c.inc(uid="u2")

    def test_cardinality_fields(self):
        card = self.c.snapshot()["cardinality"]
        self.assertEqual(card["max_series"], 1)
        self.assertEqual(card["active_series"], 1)
        self.assertEqual(card["dropped_writes"], 3)

    def test_dropped_keys_sampled(self):
        card = self.c.snapshot()["cardinality"]
        self.assertEqual(card["dropped_keys"], [{"uid": "u2"}, {"uid": "u3"}])
        self.assertFalse(card["dropped_keys_truncated"])

    def test_dropped_keys_sample_is_bounded(self):
        c = Registry().counter("hits", ["uid"], max_series=1)
        c.inc(uid="keep")
        for i in range(500):
            c.inc(uid=f"u{i}")
        card = c.snapshot()["cardinality"]
        self.assertEqual(card["dropped_writes"], 500)
        self.assertEqual(len(card["dropped_keys"]), 128)
        self.assertTrue(card["dropped_keys_truncated"])

    def test_snapshot_stays_json_serializable(self):
        json.dumps(Registry().snapshot())
        json.dumps(self.c.snapshot())


class TestRecovery(unittest.TestCase):
    def test_reset_lets_dropped_series_return(self):
        c = Registry().counter("hits", ["uid"], max_series=1)
        c.inc(uid="u1")
        c.inc(5, uid="u2")
        c.reset()
        c.inc(uid="u2")
        self.assertEqual(c.value(uid="u2"), 1)
        snap = c.snapshot()
        self.assertEqual(overflow_series(snap), [])
        self.assertEqual(snap["cardinality"]["dropped_writes"], 0)
        self.assertEqual(snap["cardinality"]["dropped_keys"], [])

    def test_reset_clears_existing_series(self):
        c = Registry().counter("hits", ["uid"], max_series=2)
        c.inc(uid="u1")
        c.reset()
        self.assertEqual(c.value(uid="u1"), 0)
        self.assertEqual(c.snapshot()["series"], [])

    def test_overflow_bucket_keeps_history_until_reset(self):
        c = Registry().counter("hits", ["uid"], max_series=1)
        c.inc(uid="u1")
        c.inc(5, uid="u2")
        c.inc(uid="u1")
        snap = c.snapshot()
        self.assertEqual(overflow_series(snap)[0]["value"], 5)
        self.assertEqual(c.value(uid="u1"), 2)


class TestConcurrency(unittest.TestCase):
    def test_concurrent_overflow_is_accurate(self):
        c = Registry().counter("hits", ["uid"], max_series=1)
        c.inc(uid="keep")
        threads = [
            threading.Thread(target=lambda n=n: [c.inc(uid=f"u{n}") for _ in range(100)])
            for n in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = c.snapshot()
        self.assertEqual(overflow_series(snap)[0]["value"], 800)
        self.assertEqual(snap["cardinality"]["dropped_writes"], 800)
        self.assertEqual(len(real_series(snap)), 1)


if __name__ == "__main__":
    unittest.main()
