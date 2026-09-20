"""TraceSampler 现有行为的锁定测试（静态模式的语义、对外接口、跨进程一致性）。"""

import os
import subprocess
import sys
import threading
import unittest

from tracesamp import ManualClock, TraceSampler, trace_unit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TRACE_IDS = ["trace-%04d" % i for i in range(20000)]


def static_decisions(sampler, trace_ids):
    return [sampler.should_sample(trace_id) for trace_id in trace_ids]


class TestStaticMode(unittest.TestCase):
    def test_same_trace_same_answer(self):
        sampler = TraceSampler(rate=0.3)
        answers = {sampler.should_sample("trace-a") for _ in range(20)}
        self.assertEqual(len(answers), 1)

    def test_ratio_matches_configured_rate(self):
        sampler = TraceSampler(rate=0.25)
        kept = sum(static_decisions(sampler, TRACE_IDS))
        ratio = kept / len(TRACE_IDS)
        self.assertAlmostEqual(ratio, 0.25, delta=0.02)

    def test_full_rate_keeps_everything(self):
        sampler = TraceSampler(rate=1.0)
        self.assertTrue(all(static_decisions(sampler, TRACE_IDS[:500])))

    def test_target_per_sec_is_ignored_in_static_mode(self):
        low = TraceSampler(rate=0.2, target_per_sec=1.0)
        high = TraceSampler(rate=0.2, target_per_sec=100000.0)
        self.assertEqual(static_decisions(low, TRACE_IDS[:2000]),
                         static_decisions(high, TRACE_IDS[:2000]))

    def test_static_rate_survives_threads(self):
        sampler = TraceSampler(rate=0.4)
        expected = static_decisions(sampler, TRACE_IDS[:200])
        collected = []
        guard = threading.Lock()

        def worker():
            got = static_decisions(sampler, TRACE_IDS[:200])
            with guard:
                collected.append(got)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(collected), 4)
        for got in collected:
            self.assertEqual(got, expected)

    def test_trace_unit_is_stable_and_in_range(self):
        for trace_id in TRACE_IDS[:1000]:
            unit = trace_unit(trace_id)
            self.assertGreaterEqual(unit, 0.0)
            self.assertLess(unit, 1.0)
            self.assertEqual(unit, trace_unit(trace_id))

    def test_decisions_do_not_depend_on_hash_seed(self):
        script = (
            "import sys;"
            "from tracesamp import TraceSampler;"
            "s = TraceSampler(rate=0.37);"
            "ids = ['trace-%04d' % i for i in range(4000)];"
            "sys.stdout.write(''.join('1' if s.should_sample(t) else '0' for t in ids))"
        )
        sampler = TraceSampler(rate=0.37)
        local = "".join("1" if s else "0"
                        for s in static_decisions(sampler, TRACE_IDS[:4000]))
        for seed in ("0", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT,
                                 env=env, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout, local)


class TestModeSwitching(unittest.TestCase):
    def test_default_mode_is_static(self):
        sampler = TraceSampler()
        self.assertEqual(sampler.mode, "static")
        self.assertEqual(sampler.rate(), 0.1)

    def test_set_mode_changes_mode_and_keeps_rate_in_range(self):
        sampler = TraceSampler(rate=0.5, target_per_sec=50.0)
        sampler.set_mode("adaptive")
        self.assertEqual(sampler.mode, "adaptive")
        self.assertGreater(sampler.rate(), 0.0)
        self.assertLessEqual(sampler.rate(), 1.0)
        sampler.set_mode("static")
        self.assertEqual(sampler.mode, "static")
        self.assertEqual(sampler.rate(), 0.5)

    def test_static_decisions_unchanged_after_adaptive_round_trip(self):
        clock = ManualClock()
        sampler = TraceSampler(rate=0.3, target_per_sec=200.0, clock=clock)
        before = static_decisions(sampler, TRACE_IDS[:1000])
        # 自适应模式下喂两秒流量，再把模式切回来
        sampler.set_mode("adaptive")
        for index in range(4000):
            sampler.should_sample(TRACE_IDS[index % 1000])
            clock.advance(0.0005)
        sampler.set_mode("static")
        self.assertEqual(static_decisions(sampler, TRACE_IDS[:1000]), before)


class TestAdaptiveSurface(unittest.TestCase):
    def test_adaptive_answers_are_booleans(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0, clock=clock)
        for index in range(300):
            self.assertIsInstance(sampler.should_sample(TRACE_IDS[index % 50]),
                                  bool)
            clock.advance(0.001)

    def test_stats_reports_the_documented_fields(self):
        sampler = TraceSampler(rate=0.5)
        stats = sampler.stats()
        for key in ("mode", "rate", "target_per_sec", "total", "sampled",
                    "dropped", "window_total", "window_sampled", "updates"):
            self.assertIn(key, stats)
        self.assertEqual(stats["mode"], "static")
        self.assertEqual(stats["rate"], 0.5)
        self.assertEqual(stats["total"], 0)

    def test_stats_counts_every_decision(self):
        sampler = TraceSampler(rate=0.5)
        for index in range(400):
            sampler.should_sample(TRACE_IDS[index])
        stats = sampler.stats()
        self.assertEqual(stats["total"], 400)
        self.assertEqual(stats["sampled"] + stats["dropped"], 400)

    def test_stats_counts_adaptive_decisions_too(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=50.0, clock=clock)
        for index in range(200):
            sampler.should_sample(TRACE_IDS[index])
            clock.advance(0.001)
        stats = sampler.stats()
        self.assertEqual(stats["mode"], "adaptive")
        self.assertEqual(stats["total"], 200)


class TestValidation(unittest.TestCase):
    def test_rate_bounds(self):
        for bad in (0.0, -0.5, 1.5):
            with self.assertRaises(ValueError):
                TraceSampler(rate=bad)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            TraceSampler(mode="dynamic")
        sampler = TraceSampler()
        with self.assertRaises(ValueError):
            sampler.set_mode("dynamic")

    def test_target_and_window_must_be_positive(self):
        with self.assertRaises(ValueError):
            TraceSampler(target_per_sec=0.0)
        with self.assertRaises(ValueError):
            TraceSampler(window_seconds=0.0)


if __name__ == "__main__":
    unittest.main()
