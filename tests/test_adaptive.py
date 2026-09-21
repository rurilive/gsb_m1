"""自适应模式的回归测试：收敛行为、trace 一致性、并发安全。

不动 tests/ 里已有的基线，这里只锁自适应模式要满足的新行为。
"""

import threading
import unittest

from tracesamp import ManualClock, SlidingWindow, TraceSampler, trace_unit
from tracesamp.controller import RateController


def pump(sampler, clock, spans_per_second, seconds, tag, spans_per_trace=3):
    """灌 seconds 秒的流量，返回每一秒采到的条数列表。"""
    total = int(spans_per_second * seconds)
    step = 1.0 / spans_per_second
    per_second = []
    kept = 0
    for index in range(total):
        if sampler.should_sample("%s-%d" % (tag, index // spans_per_trace)):
            kept += 1
        clock.advance(step)
        if (index + 1) % int(spans_per_second) == 0:
            per_second.append(kept)
            kept = 0
    return per_second


class TestWindowRotation(unittest.TestCase):
    def test_recent_bucket_survives_rotation(self):
        # 滚一格不该把还在窗口里的数据清掉
        clock = ManualClock()
        window = SlidingWindow(1.0, 2, clock)
        window.add("total", 5)
        clock.advance(0.6)
        self.assertEqual(window.count("total"), 5)

    def test_old_bucket_expires_after_full_window(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 2, clock)
        window.add("total", 5)
        clock.advance(1.1)
        self.assertEqual(window.count("total"), 0)

    def test_counts_reads_multiple_keys_together(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 2, clock)
        window.add("total", 4)
        window.add("sampled", 1)
        self.assertEqual(window.counts(("total", "sampled")),
                         {"total": 4, "sampled": 1})


class TestRateController(unittest.TestCase):
    def make_controller(self, target=150.0):
        clock = ManualClock()
        return RateController(target, clock=clock), clock

    def test_converges_down_to_target_ratio(self):
        controller, _ = self.make_controller()
        for _ in range(30):
            controller.observe(1200.0 * controller.rate(), 1200.0)
        self.assertAlmostEqual(controller.rate(), 150.0 / 1200.0, delta=0.01)

    def test_recovers_when_traffic_calms(self):
        controller, _ = self.make_controller(target=200.0)
        for _ in range(30):
            controller.observe(4000.0 * controller.rate(), 4000.0)
        self.assertLess(controller.rate(), 0.1)
        for _ in range(30):
            controller.observe(300.0 * controller.rate(), 300.0)
        self.assertAlmostEqual(controller.rate(), 200.0 / 300.0, delta=0.05)

    def test_holds_inside_deadband(self):
        controller, _ = self.make_controller()
        for _ in range(30):
            controller.observe(1200.0 * controller.rate(), 1200.0)
        rate = controller.rate()
        updates = controller.updates()
        # 采样量落在目标上下 10% 以内就不该再动
        controller.observe(150.0 * 1.05, 1200.0)
        controller.observe(150.0 * 0.95, 1200.0)
        self.assertEqual(controller.rate(), rate)
        self.assertEqual(controller.updates(), updates)

    def test_single_step_is_bounded(self):
        controller, _ = self.make_controller()
        controller.observe(100000.0, 100000.0)
        self.assertGreaterEqual(controller.rate(), 0.5)
        for _ in range(60):
            controller.observe(0.0, 100000.0)
        self.assertGreater(controller.rate(), 0.0)

    def test_rate_stays_in_bounds(self):
        controller, _ = self.make_controller()
        for total in (1.0, 10.0, 1000.0, 1000000.0):
            for _ in range(10):
                rate = controller.observe(total * controller.rate(), total)
                self.assertGreater(rate, 0.0)
                self.assertLessEqual(rate, 1.0)

    def test_low_traffic_pins_at_full_rate(self):
        controller, _ = self.make_controller()
        for _ in range(30):
            controller.observe(80.0 * controller.rate(), 80.0)
        # 流量低于目标时全采，采样率停在 1.0 且不再抖动
        self.assertEqual(controller.rate(), 1.0)
        updates = controller.updates()
        controller.observe(80.0, 80.0)
        self.assertEqual(controller.updates(), updates)


class TestAdaptiveConvergence(unittest.TestCase):
    def test_steady_traffic_hugs_target(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0, clock=clock)
        per_second = pump(sampler, clock, 1200, 8, "steady")
        for kept in per_second[3:]:
            self.assertGreater(kept, 90)
            self.assertLess(kept, 220)
        # 收敛之后采样率不再大幅摆动
        rate = sampler.rate()
        pump(sampler, clock, 1200, 2, "steady-more")
        self.assertAlmostEqual(sampler.rate(), rate, delta=0.05)

    def test_burst_then_calm_settles_back(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0, clock=clock)
        pump(sampler, clock, 4000, 3, "burst")
        self.assertLess(sampler.rate(), 0.2)
        calm = pump(sampler, clock, 300, 8, "calm")
        for kept in calm[4:]:
            self.assertGreater(kept, 120)
            self.assertLess(kept, 290)
        self.assertLess(sampler.rate(), 1.0)


class TestTraceConsistency(unittest.TestCase):
    def make_sampler(self, target=150.0):
        clock = ManualClock()
        return TraceSampler(mode="adaptive", target_per_sec=target,
                            clock=clock), clock

    def test_spans_arriving_seconds_apart_agree(self):
        sampler, clock = self.make_sampler()
        pump(sampler, clock, 3000, 2, "warmup")
        answers = set()
        for _ in range(12):
            answers.add(sampler.should_sample("trace-slow"))
            clock.advance(0.5)
        self.assertEqual(len(answers), 1)

    def test_concurrent_spans_of_one_trace_agree(self):
        sampler, clock = self.make_sampler()
        pump(sampler, clock, 3000, 2, "warmup")
        results = []
        barrier = threading.Barrier(8)
        guard = threading.Lock()

        def worker():
            barrier.wait()
            local = [sampler.should_sample("trace-hot") for _ in range(6)]
            with guard:
                results.extend(local)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 48)
        self.assertEqual(len(set(results)), 1)

    def test_decision_matches_trace_unit_threshold(self):
        sampler, clock = self.make_sampler()
        pump(sampler, clock, 3000, 2, "warmup")
        rate = sampler.rate()
        for index in range(200):
            trace_id = "probe-%d" % index
            expected = trace_unit(trace_id) < rate
            self.assertEqual(sampler.should_sample(trace_id), expected)

    def test_decision_cache_expires(self):
        sampler, clock = self.make_sampler()
        first = sampler.should_sample("trace-ephemeral")
        clock.advance(3600.0)
        # 缓存早已过期，重新按当时的采样率算，不报错也不卡住
        self.assertIn(sampler.should_sample("trace-ephemeral"), (True, False))
        self.assertIn(first, (True, False))


class TestAdaptiveThreads(unittest.TestCase):
    def test_mixed_traffic_under_threads(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0, clock=clock)
        barrier = threading.Barrier(8)
        errors = []

        def worker(worker_id):
            barrier.wait()
            try:
                for index in range(2000):
                    sampler.should_sample("w%d-%d" % (worker_id, index // 3))
                    if index % 200 == 0:
                        clock.advance(0.01)
            except Exception as exc:  # pragma: no cover - 失败时带出来
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        stats = sampler.stats()
        self.assertEqual(stats["total"], 8 * 2000)
        self.assertEqual(stats["sampled"] + stats["dropped"], stats["total"])
        self.assertGreater(stats["rate"], 0.0)
        self.assertLessEqual(stats["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
