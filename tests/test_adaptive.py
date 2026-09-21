"""自适应模式的行为测试（新文件，基线测试一个字没动）。

覆盖四类线上事故的回归：

1. 同一条 trace 的 span 结论必须一致，跨秒、跨阈值变化、并发都一样；
2. 采样量贴着 target_per_sec 收敛，小幅流量波动不抖，峰值过后沉得回来；
3. 控制器不砸地板、不钉 1.0，脏读数有限幅保护；
4. SlidingWindow 是真滑动窗口，total/sampled 多键读写一致。
"""

import threading
import unittest

from tracesamp import ManualClock, SlidingWindow, TraceSampler
from tracesamp.controller import RateController


def pump(sampler, clock, spans_per_second, seconds, tag,
         spans_per_trace=3, tick=None):
    """灌 seconds 秒流量，返回每秒采样条数列表。"""
    total = int(spans_per_second * seconds)
    step = 1.0 / spans_per_second
    per_second = []
    kept = 0
    for index in range(total):
        if sampler.should_sample("%s-%d" % (tag, index // spans_per_trace)):
            kept += 1
        clock.advance(step)
        if tick is not None:
            tick(index)
        if (index + 1) % int(spans_per_second) == 0:
            per_second.append(kept)
            kept = 0
    return per_second


class TestTraceConsistency(unittest.TestCase):
    def test_same_trace_consistent_across_seconds(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        # 先灌流量让采样率发生多次变化
        pump(sampler, clock, 3000, 2, "warmup")
        first = sampler.should_sample("trace-late")
        answers = [first]
        # 同一条 trace 的 span 陆续在 6 秒内到齐，期间采样率一直在变
        for _ in range(20):
            clock.advance(0.3)
            pump(sampler, clock, 2000, 0.3, "bg")
            answers.append(sampler.should_sample("trace-late"))
        self.assertTrue(all(a == first for a in answers))

    def test_same_trace_consistent_under_concurrency(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        pump(sampler, clock, 3000, 1, "warmup")
        barrier = threading.Barrier(8)
        results = []
        guard = threading.Lock()

        def worker():
            barrier.wait()
            local = [sampler.should_sample("trace-hot") for _ in range(50)]
            with guard:
                results.extend(local)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 400)
        self.assertTrue(all(a == results[0] for a in results))

    def test_decision_is_deterministic_for_a_trace(self):
        # 同一个 rate 下，一条 trace 第一次拍板跟 trace_unit 比较结果一致
        from tracesamp.sampler import _DecisionCache, trace_unit
        clock = ManualClock()
        cache = _DecisionCache(clock)
        rate = 0.3
        for trace_id in ("t-a", "t-b", "t-c"):
            expected = trace_unit(trace_id) < rate
            self.assertIs(cache.get_or_decide(trace_id, rate), expected)
            # rate 之后变了，旧结论仍然钉住
            self.assertIs(cache.get_or_decide(trace_id, 0.999), expected)
            self.assertIs(cache.get_or_decide(trace_id, 0.001), expected)

    def test_decision_expires_after_ttl(self):
        from tracesamp.sampler import _DecisionCache, trace_unit
        clock = ManualClock()
        cache = _DecisionCache(clock, shards=4, capacity=100, ttl_seconds=1.0)
        # 找一条在 0.2 下不采、在 0.8 下会采的 trace
        trace_id = next(t for t in ("t%d" % i for i in range(1000))
                        if 0.2 <= trace_unit(t) < 0.8)
        self.assertIs(cache.get_or_decide(trace_id, 0.2), False)
        clock.advance(0.5)
        self.assertIs(cache.get_or_decide(trace_id, 0.8), False)  # TTL 内钉住
        clock.advance(1.1)
        self.assertIs(cache.get_or_decide(trace_id, 0.8), True)  # 过期重拍

    def test_decision_cache_is_bounded_by_lru(self):
        from tracesamp.sampler import _DecisionCache
        clock = ManualClock()
        cache = _DecisionCache(clock, shards=1, capacity=10, ttl_seconds=999.0)
        for i in range(30):
            cache.get_or_decide("t%d" % i, 0.5)
        self.assertEqual(len(cache._entries[0]), 10)
        # 最老的已被淘汰，重新出现会按新 rate 拍板
        self.assertIsNotNone(cache.get_or_decide("t0", 1.0))


class TestConvergence(unittest.TestCase):
    def test_steady_traffic_converges_to_target(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        per_second = pump(sampler, clock, 1200, 8, "steady")
        # 稳态（第 3 秒起）每秒采样量贴着 150，容忍 20%
        for value in per_second[2:]:
            self.assertAlmostEqual(value, 150, delta=30)
        # 稳态采样率收敛到 target/total，不再乱动
        self.assertAlmostEqual(sampler.rate(), 150 / 1200, delta=0.02)

    def test_recovers_after_burst(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 4000, 3, "burst")
        rate_after_burst = sampler.rate()
        self.assertLess(rate_after_burst, 0.2)
        calm = pump(sampler, clock, 300, 6, "calm")
        # 给一拍恢复时间，之后贴着 200；且采样率不再钉在 1.0
        for value in calm[2:]:
            self.assertAlmostEqual(value, 200, delta=45)
        self.assertLess(sampler.rate(), 0.9)
        self.assertGreater(sampler.rate(), rate_after_burst)

    def test_below_target_samples_everything(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=10000.0,
                               clock=clock)
        per_second = pump(sampler, clock, 300, 3, "low")
        for value in per_second[1:]:
            self.assertEqual(value, 300)
        self.assertEqual(sampler.rate(), 1.0)

    def test_small_traffic_wobble_does_not_chase_rate(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 1000, 3, "settle")
        rate_before = sampler.rate()
        # 流量在 ±5% 内小幅抖动两秒
        for second in range(8):
            rate_here = 1000 + (50 if second % 2 else -50)
            pump(sampler, clock, rate_here, 0.25, "wobble-%d" % second)
        self.assertAlmostEqual(sampler.rate(), rate_before, delta=0.01)


class TestController(unittest.TestCase):
    def test_rate_moves_both_directions(self):
        controller = RateController(100.0, clock=ManualClock())
        controller.observe(100.0, 1000.0)   # 期望 0.1
        self.assertAlmostEqual(controller.rate(), 0.1, places=6)
        controller.observe(0.0, 500.0)      # 流量回落，期望 0.2，必须升得回来
        self.assertGreater(controller.rate(), 0.1)

    def test_zero_sampled_with_traffic_does_not_slam_to_max(self):
        controller = RateController(100.0, clock=ManualClock())
        controller.observe(100.0, 1000.0)
        controller.observe(0.0, 1000.0)     # 这拍没采到不是阈值的错
        self.assertLess(controller.rate(), 0.2)

    def test_no_traffic_holds_rate(self):
        controller = RateController(200.0, clock=ManualClock())
        controller.observe(100.0, 2000.0)
        held = controller.rate()
        for _ in range(5):
            returned = controller.observe(0.0, 0.0)
        self.assertEqual(returned, held)
        self.assertEqual(controller.rate(), held)

    def test_step_change_is_clamped(self):
        controller = RateController(100.0, clock=ManualClock())
        controller.observe(100.0, 1000.0)   # 0.1
        # 脏读数：两个计数读岔，total 显得是天文数字，也不能一步砸到地板
        controller.observe(0.0, 1000000.0)
        self.assertGreaterEqual(controller.rate(), 0.1 / 10.0)

    def test_reset_returns_to_max_and_primes_again(self):
        controller = RateController(100.0, clock=ManualClock())
        controller.observe(100.0, 1000.0)
        self.assertLess(controller.rate(), 1.0)
        controller.reset()
        self.assertEqual(controller.rate(), 1.0)
        self.assertEqual(controller.updates(), 0)


class TestSlidingWindowSemantics(unittest.TestCase):
    def test_counts_survive_bucket_rollover(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 4, clock)
        window.add("total", 10)
        clock.advance(0.25)
        window.add("total", 5)
        # 跨过桶边界后，旧桶的数据仍在窗口内，不能整窗清空
        clock.advance(0.01)
        self.assertEqual(window.count("total"), 15)

    def test_old_buckets_expire_one_by_one(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 4, clock)
        window.add("total", 10)   # bucket 0
        clock.advance(0.3)
        window.add("total", 20)   # bucket 1
        clock.advance(0.3)
        window.add("total", 30)   # bucket 2
        clock.advance(0.5)        # bucket 0 的数据滑出
        self.assertEqual(window.count("total"), 50)

    def test_snapshot_reads_keys_consistently(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 2, clock)
        window.add_many((("total", 8), ("sampled", 2)))
        snap = window.snapshot(("total", "sampled", "dropped"))
        self.assertEqual(snap, {"total": 8, "sampled": 2, "dropped": 0})

    def test_rates_accounts_for_partial_window_at_start(self):
        clock = ManualClock()
        window = SlidingWindow(1.0, 4, clock)
        window.add("total", 100)
        clock.advance(0.1)
        # 只跑了 0.1 秒就有 100 条，折算每秒应约 1000，而不是 100
        rates = window.rates(("total",))
        self.assertAlmostEqual(rates["total"], 1000.0, delta=50.0)


class TestModeSwitchingAdaptive(unittest.TestCase):
    def test_reentering_adaptive_resets_rate_and_decisions(self):
        clock = ManualClock()
        sampler = TraceSampler(rate=0.5, target_per_sec=100.0, clock=clock)
        sampler.set_mode("adaptive")
        pump(sampler, clock, 2000, 2, "round1")
        self.assertLess(sampler.rate(), 0.2)
        sampler.set_mode("static")
        sampler.set_mode("adaptive")
        self.assertEqual(sampler.rate(), 1.0)
        self.assertEqual(sampler.stats()["updates"], 0)

    def test_static_semantics_unchanged_after_all_this(self):
        clock = ManualClock()
        sampler = TraceSampler(rate=0.25, clock=clock)
        kept = sum(sampler.should_sample("t%05d" % i) for i in range(20000))
        self.assertAlmostEqual(kept / 20000, 0.25, delta=0.02)


if __name__ == "__main__":
    unittest.main()
