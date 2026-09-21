"""自适应模式重做后的行为测试（基线 tests/test_*.py 不覆盖的部分）。"""

import threading
import unittest

from tracesamp import ManualClock, TraceSampler, trace_unit
from tracesamp.controller import RateController
from tracesamp.window import SlidingWindow


def pump(sampler, clock, spans_per_second, seconds, tag,
         spans_per_trace=3):
    """灌 seconds 秒流量，返回每秒采样条数列表。"""
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


class TestTraceConsistency(unittest.TestCase):
    def test_spans_several_seconds_apart_agree(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        first = sampler.should_sample("trace-long")
        # 中间穿插别的流量，再隔 4 秒（在决策 TTL 内）继续问同一条 trace
        pump(sampler, clock, 2000, 4.0, "noise")
        later = sampler.should_sample("trace-long")
        self.assertIs(first, later)

    def test_concurrent_spans_of_one_trace_agree(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)

        def ask_same_trace(results, barrier):
            barrier.wait()
            results.append(sampler.should_sample("trace-hot"))

        for _ in range(6):
            results = []
            barrier = threading.Barrier(8)
            threads = [threading.Thread(target=ask_same_trace,
                                        args=(results, barrier))
                       for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(set(results)), 1)
            clock.advance(0.01)

    def test_decision_is_unit_against_rate_at_first_sight(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        # 强迫控制器到一个已知的中间档位
        pump(sampler, clock, 1000, 2.0, "force-rate")
        rate = sampler.rate()
        trace_id = "fresh-trace-xyz"
        expected = trace_unit(trace_id) < rate
        self.assertIs(sampler.should_sample(trace_id), expected)
        # 之后档位就算变了，同一条 trace 的结论也不变（TTL 内）
        pump(sampler, clock, 4000, 2.0, "shift-rate")
        self.assertIs(sampler.should_sample(trace_id), expected)

    def test_expired_trace_is_redecided_at_current_rate(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               decision_ttl=0.5, clock=clock)
        first = sampler.should_sample("trace-ttl")
        pump(sampler, clock, 4000, 1.0, "gap")
        # 超过 TTL 后允许按新档位重新决策；无论结论是什么，新的结论必须
        # 对该 trace 再次稳定
        second = sampler.should_sample("trace-ttl")
        third = sampler.should_sample("trace-ttl")
        self.assertIs(second, third)
        self.assertIsInstance(first, bool)


class TestConvergence(unittest.TestCase):
    def test_steady_traffic_converges_to_target(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        per_second = pump(sampler, clock, 1200, 8.0, "steady")
        # 第 1 秒是冷启动（初始档位 1.0），跳过；冷启动后一拍有余波，
        # 之后贴着目标小幅走。回放里每秒只有 400 个不同 trace，集合本身
        # 的散列噪声就有几十条，所以逐秒用宽限，均值用紧限。
        settled = per_second[3:]
        for sampled in settled:
            self.assertAlmostEqual(sampled, 150, delta=50)
        tail = per_second[5:]
        self.assertAlmostEqual(sum(tail) / len(tail), 150, delta=20)
        # 关键：绝不能再出现旧版那种长期 4-5 倍目标的采样量
        self.assertLess(max(settled), 300)

    def test_sampled_never_exceeds_target_by_much_after_warmup(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        per_second = pump(sampler, clock, 1200, 8.0, "steady")
        # 冷启动后的余波可能略高，之后不应再冲到目标的 1.5 倍以上
        for sampled in per_second[3:]:
            self.assertLessEqual(sampled, 225)

    def test_burst_rate_comes_back_down_after_traffic_drops(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 4000, 3.0, "burst")
        rate_after_burst = sampler.rate()
        self.assertLess(rate_after_burst, 0.2)
        calm = pump(sampler, clock, 300, 6.0, "calm")
        for sampled in calm[2:]:
            self.assertAlmostEqual(sampled, 200, delta=45)
        self.assertLess(sampler.rate(), 0.9)

    def test_rate_stays_below_one_and_above_floor(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        pump(sampler, clock, 20000, 3.0, "heavy")
        self.assertGreater(sampler.rate(), 0.0)
        self.assertLessEqual(sampler.rate(), 1.0)
        # 目标 100 / 20000 = 0.005，控制器不该一步砸到 min 档 0.001
        self.assertGreater(sampler.rate(), 0.001)

    def test_no_traffic_does_not_move_rate(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        pump(sampler, clock, 1000, 2.0, "some")
        rate = sampler.rate()
        clock.advance(5.0)
        # 没有 span 就没有控制推进，档位原样
        self.assertEqual(sampler.rate(), rate)

    def test_low_traffic_samples_everything(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=1000.0,
                               clock=clock)
        per_second = pump(sampler, clock, 100, 4.0, "thin",
                          spans_per_trace=1)
        # 每秒 100 条全采，档位停在 1.0，不会被什么反馈砸下去
        self.assertEqual(per_second, [100, 100, 100, 100])
        self.assertEqual(sampler.rate(), 1.0)


class TestModeReset(unittest.TestCase):
    def test_reentering_adaptive_resets_window_and_rate(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        pump(sampler, clock, 5000, 2.0, "load")
        self.assertLess(sampler.rate(), 0.1)
        sampler.set_mode("static")
        sampler.set_mode("adaptive")
        self.assertEqual(sampler.rate(), 1.0)
        self.assertEqual(sampler.stats()["window_total"], 0)
        self.assertEqual(sampler.stats()["updates"], 0)


class TestSlidingWindowFixes(unittest.TestCase):
    def test_buckets_expire_one_at_a_time_not_all_at_once(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 4, clock)
        window.add("total", 10)          # 桶 0：[0, .25)
        clock.advance(0.25)
        window.add("total", 10)          # 桶 1
        clock.advance(0.25)
        window.add("total", 10)          # 桶 2
        # 进入桶 3 时，桶 0 还在窗口内，一个桶都不该丢
        clock.advance(0.25)
        self.assertEqual(window.count("total"), 30)
        # 再进一格，桶 0 才滑出
        clock.advance(0.25)
        self.assertEqual(window.count("total"), 20)

    def test_snapshot_reads_keys_from_one_consistent_state(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 2, clock)
        window.add2("total", 1, "sampled", 1)
        clock.advance(0.5)
        window.add2("total", 3, "sampled", 1)
        (total, sampled), coverage = window.snapshot(
            ("total", "sampled"))
        self.assertEqual(total, 4)
        self.assertEqual(sampled, 2)
        self.assertEqual(coverage, 1.0)

    def test_snapshot_coverage_tracks_partial_window(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 4, clock)
        window.add("total", 10)
        clock.advance(0.25)
        (count,), coverage = window.snapshot(("total",))
        self.assertEqual(count, 10)
        self.assertAlmostEqual(coverage, 0.5)

    def test_snapshot_after_long_idle_is_empty(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 4, clock)
        window.add("total", 10)
        clock.advance(30.0)
        (count,), coverage = window.snapshot(("total",))
        self.assertEqual(count, 0)
        self.assertEqual(coverage, 0.0)


class TestRateControllerLaw(unittest.TestCase):
    def test_rate_moves_symmetrical_up_and_down(self):
        controller = RateController(target_per_sec=100.0)
        # 总吞吐 2000/s -> 目标档位 0.05
        rate = controller.observe(100.0, 2000.0)
        self.assertLess(rate, 1.0)
        for _ in range(20):
            rate = controller.observe(rate * 2000.0, 2000.0)
        self.assertAlmostEqual(rate, 0.05, delta=0.005)
        # 总吞吐回落到 200/s -> 目标档位 0.5，必须升得回来
        for _ in range(20):
            rate = controller.observe(rate * 200.0, 200.0)
        self.assertAlmostEqual(rate, 0.5, delta=0.05)

    def test_zero_sampled_does_not_pin_rate_to_max(self):
        controller = RateController(target_per_sec=100.0)
        for _ in range(20):
            rate = controller.observe(1.0, 2000.0)
        low = rate
        self.assertLess(low, 0.1)
        # 某窗一条没采到（sampled=0）：只按总吞吐走，不拍 1.0
        rate = controller.observe(0.0, 2000.0)
        self.assertLess(rate, 0.1)

    def test_zero_traffic_keeps_rate(self):
        controller = RateController(target_per_sec=100.0)
        controller.observe(100.0, 2000.0)
        rate = controller.rate()
        self.assertEqual(controller.observe(0.0, 0.0), rate)

    def test_rate_is_clamped_to_bounds(self):
        controller = RateController(target_per_sec=100.0, min_rate=0.01)
        for _ in range(30):
            rate = controller.observe(1.0, 100000.0)
        self.assertGreaterEqual(rate, 0.01)
        thin = RateController(target_per_sec=1000.0)
        for _ in range(5):
            value = thin.observe(100.0, 100.0)
        self.assertEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
