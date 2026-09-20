"""metrio.meters 行为清单——重构期间一个字都不改，必须原样全绿。"""

import json
import unittest

from metrio import (
    counter_value,
    export_json,
    export_prom,
    histogram,
    inc,
    observe,
    render_text,
    reset,
)


class TestCounters(unittest.TestCase):
    def setUp(self):
        reset()

    def test_inc_default_one(self):
        inc("a")
        self.assertEqual(counter_value("a"), 1)

    def test_inc_explicit_n(self):
        inc("a", 40)
        self.assertEqual(counter_value("a"), 40)

    def test_inc_negative_allowed(self):
        inc("a", 10)
        inc("a", -3)
        self.assertEqual(counter_value("a"), 7)

    def test_inc_returns_new_value(self):
        self.assertEqual(inc("a"), 1)
        self.assertEqual(inc("a", 2), 3)

    def test_inc_repeats_do_not_duplicate_registration(self):
        inc("a")
        inc("a")
        doc = json.loads(export_json())
        self.assertEqual(len(doc["counters"]), 1)

    def test_counter_value_unknown_default_zero(self):
        self.assertEqual(counter_value("nope"), 0)

    def test_counter_value_unknown_explicit_default(self):
        self.assertEqual(counter_value("nope", 5), 5)

    def test_inc_rejects_float_n(self):
        with self.assertRaises(TypeError):
            inc("a", 1.5)

    def test_counter_and_histogram_namespaces_independent(self):
        inc("x")
        observe("x", 1.0)
        self.assertEqual(counter_value("x"), 1)
        doc = json.loads(export_json())
        self.assertEqual(len(doc["histograms"]), 1)
        self.assertEqual(doc["histograms"][0]["count"], 1)


class TestObserve(unittest.TestCase):
    def setUp(self):
        reset()

    def test_single_sample_stats(self):
        observe("h", 3.5)
        doc = json.loads(export_json())
        h = doc["histograms"][0]
        self.assertEqual(h["count"], 1)
        self.assertEqual(h["sum"], 3.5)
        self.assertEqual(h["avg"], 3.5)
        self.assertEqual(h["min"], 3.5)
        self.assertEqual(h["max"], 3.5)

    def test_sample_order_does_not_matter(self):
        for v in (12.0, 31.5, 7.25, 120.0, 44.5):
            observe("h", v)
        a = export_json()
        reset()
        for v in (44.5, 7.25, 120.0, 12.0, 31.5):
            observe("h", v)
        self.assertEqual(export_json(), a)

    def test_negative_samples_allowed(self):
        observe("h", -2.0)
        observe("h", 4.0)
        doc = json.loads(export_json())
        self.assertEqual(doc["histograms"][0]["min"], -2.0)
        self.assertEqual(doc["histograms"][0]["max"], 4.0)

    def test_observe_registers_lazy(self):
        observe("h", 1.0)
        self.assertIn("h", export_json())


class TestPercentiles(unittest.TestCase):
    def setUp(self):
        reset()

    def _json(self, values):
        for v in values:
            observe("h", v)
        return json.loads(export_json())["histograms"][0]

    def test_p50_odd_count(self):
        h = self._json([1.0, 2.0, 3.0])
        self.assertEqual(h["p50"], 2.0)

    def test_p50_even_count_lower_middle(self):
        # 最近秩法的历史行为：偶数个样本取中间偏下的那个，不是平均
        h = self._json([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(h["p50"], 2.0)

    def test_p95_small_count_hits_max(self):
        h = self._json([1.0, 2.0, 3.0])
        self.assertEqual(h["p95"], 3.0)

    def test_p999_clamped_to_max(self):
        h = self._json([1.0, 2.0, 3.0])
        self.assertEqual(h["p999"], 3.0)

    def test_single_sample_all_pctls_equal_value(self):
        h = self._json([7.5])
        self.assertEqual(h["p50"], 7.5)
        self.assertEqual(h["p95"], 7.5)
        self.assertEqual(h["p999"], 7.5)


class TestRenderText(unittest.TestCase):
    def setUp(self):
        reset()

    def test_empty_registry_renders_empty_string(self):
        self.assertEqual(render_text(), "")

    def test_counters_only(self):
        inc("b", 2)
        inc("a")
        self.assertEqual(render_text(), "counters:\n  b = 2\n  a = 1")

    def test_histogram_only(self):
        for v in (12.0, 31.5, 7.25, 120.0, 44.5):
            observe("latency.ms", v)
        self.assertEqual(
            render_text(),
            "histograms:\n"
            "  latency.ms n=5 avg=43.05 min=7.25 max=120.00 p50=31.50 p95=120.00",
        )

    def test_full_render_byte_exact(self):
        inc("http.requests")
        inc("http.requests")
        inc("http.requests", 40)
        inc("cache.hits", 7)
        inc("cache.miss")
        inc("gc.pause", -1)
        observe("latency.ms", 12.0)
        observe("latency.ms", 31.5)
        observe("latency.ms", 7.25)
        observe("latency.ms", 120.0)
        observe("latency.ms", 44.5)
        observe("size.kb", 3.5)
        observe("size.kb", 8.0)
        observe("size.kb", 2.25)
        self.assertEqual(
            render_text(),
            "counters:\n"
            "  http.requests = 42\n"
            "  cache.hits = 7\n"
            "  cache.miss = 1\n"
            "  gc.pause = -1\n"
            "histograms:\n"
            "  latency.ms n=5 avg=43.05 min=7.25 max=120.00 p50=31.50 p95=120.00\n"
            "  size.kb n=3 avg=4.58 min=2.25 max=8.00 p50=3.50 p95=8.00",
        )

    def test_avg_always_two_decimals(self):
        observe("h", 3.0)
        observe("h", 4.0)
        self.assertIn("avg=3.50", render_text())

    def test_empty_histogram_renders_zeros(self):
        histogram("e")
        self.assertEqual(
            render_text(),
            "histograms:\n"
            "  e n=0 avg=0.00 min=0.00 max=0.00 p50=0.00 p95=0.00",
        )


class TestExportJson(unittest.TestCase):
    def setUp(self):
        reset()

    def test_empty_json(self):
        self.assertEqual(export_json(), '{"counters": [], "histograms": []}')

    def test_counters_only_exact(self):
        inc("a")
        inc("b", 2)
        self.assertEqual(
            export_json(),
            '{"counters": [{"name": "a", "value": 1}, {"name": "b", "value": 2}], "histograms": []}',
        )

    def test_single_sample_exact(self):
        observe("h", 3.5)
        self.assertEqual(
            export_json(),
            '{"counters": [], "histograms": [{"name": "h", "count": 1, "sum": 3.5, '
            '"avg": 3.5, "min": 3.5, "max": 3.5, "p50": 3.5, "p95": 3.5, "p999": 3.5}]}',
        )

    def test_counter_entry_field_order(self):
        inc("a")
        doc = json.loads(export_json(), object_pairs_hook=list)
        counters = [v for k, v in doc if k == "counters"][0]
        self.assertEqual(counters[0], [("name", "a"), ("value", 1)])

    def test_histogram_entry_field_order(self):
        observe("h", 1.0)
        doc = json.loads(export_json(), object_pairs_hook=list)
        histos = [v for k, v in doc if k == "histograms"][0]
        self.assertEqual(
            [k for k, _ in histos[0]],
            ["name", "count", "sum", "avg", "min", "max", "p50", "p95", "p999"],
        )

    def test_export_order_is_registration_order(self):
        inc("zebra")
        inc("alpha")
        inc("mid")
        doc = json.loads(export_json())
        self.assertEqual(
            [c["name"] for c in doc["counters"]], ["zebra", "alpha", "mid"]
        )


class TestExportProm(unittest.TestCase):
    def setUp(self):
        reset()

    def test_empty_prom(self):
        self.assertEqual(export_prom(), "")

    def test_counter_exact(self):
        inc("a", 5)
        self.assertEqual(export_prom(), "# TYPE a counter\na 5")

    def test_single_sample_exact(self):
        observe("h", 3.5)
        self.assertEqual(
            export_prom(),
            '# TYPE h summary\n'
            'h{quantile="0.5"} 3.5\n'
            'h{quantile="0.95"} 3.5\n'
            'h{quantile="0.999"} 3.5\n'
            "h_count 1\n"
            "h_sum 3.5",
        )

    def test_empty_histogram_has_no_quantile_lines(self):
        histogram("e")
        self.assertEqual(export_prom(), "# TYPE e summary\ne_count 0\ne_sum 0")

    def test_prom_field_order_quantile_before_count(self):
        observe("h", 1.0)
        observe("h", 2.0)
        out = export_prom()
        self.assertLess(out.index('quantile="0.5"'), out.index("_count"))
        self.assertLess(out.index("_count"), out.index("_sum"))

    def test_prom_count_before_sum(self):
        observe("h", 1.0)
        out = export_prom()
        self.assertLess(out.index("h_count"), out.index("h_sum"))


class TestReset(unittest.TestCase):
    def setUp(self):
        reset()

    def test_reset_clears_everything(self):
        inc("a")
        observe("h", 1.0)
        reset()
        self.assertEqual(render_text(), "")
        self.assertEqual(export_json(), '{"counters": [], "histograms": []}')
        self.assertEqual(counter_value("a"), 0)

    def test_reuse_after_reset(self):
        inc("a")
        reset()
        inc("b")
        self.assertEqual(
            render_text(),
            "counters:\n  b = 1",
        )


if __name__ == "__main__":
    unittest.main()
