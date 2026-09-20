"""自适应采样器的行为测试：trace 一致性、收敛、峰值回落、并发与缓存。

这些是新自适应路径的专项测试，静态语义基线仍在 test_sampler.py 里
原封不动地锁着。
"""

import threading
import unittest

from tracesamp import ManualClock, TraceSampler, trace_unit
from tracesamp.sampler import DecisionCache


def pump(sampler, clock, spans_per_second, seconds, tag,
         spans_per_trace=3):
    """按 spans_per_second 的密度灌 seconds 秒，返回每秒采样条数。"""
    total = int(spans_per_second * seconds)
    step = 1.0 / spans_per_second
    per_second = []
    kept = 0
    for index in range(total):
        trace_id = "%s-%d" % (tag, index // spans_per_trace)
        if sampler.should_sample(trace_id):
            kept += 1
        clock.advance(step)
        if (index + 1) % int(spans_per_second) == 0:
            per_second.append(kept)
            kept = 0
    return per_second


class TestTraceDecisionConsistency(unittest.TestCase):
    def test_spans_seconds_apart_get_one_answer(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        pump(sampler, clock, 3000, 2.0, "warmup")
        expected = sampler.should_sample("trace-slow")
        # 真实场景：服务一直在收别的 trace，同一条 trace 的 span 隔
        # 几百毫秒陆续到。背景流量让采样率稳定，缓存换代后按同一
        # trace_id、同一采样率重新决策，结论依然不变。
        answers = [expected]
        for index in range(12):
            answers.append(sampler.should_sample("trace-slow"))
            pump(sampler, clock, 3000, 0.25, "bg-%d" % index)
        self.assertEqual(set(answers), {expected})

    def test_redecision_after_eviction_matches_when_rate_unchanged(self):
        # 不经过缓存、同一采样率下直接重算，结论必须一致
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        pump(sampler, clock, 3000, 2.0, "warmup")
        rate = sampler.rate()
        first = trace_unit("trace-late") < rate
        # 清空缓存模拟条目早已被换代淘汰
        sampler._cache.clear()
        clock.advance(0.01)
        self.assertEqual(sampler.should_sample("trace-late"), first)

    def test_burst_of_spans_get_one_answer(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        pump(sampler, clock, 3000, 1.0, "warmup")
        answers = {sampler.should_sample("trace-burst") for _ in range(64)}
        self.assertEqual(len(answers), 1)

    def test_concurrent_spans_of_one_trace_agree(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        pump(sampler, clock, 2000, 1.0, "warmup")
        pool = []
        guard = threading.Lock()
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()
            keep = sampler.should_sample("trace-concurrent")
            with guard:
                pool.append(keep)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertIn(pool.count(True), (0, 8))


class TestConvergence(unittest.TestCase):
    def test_steady_traffic_tracks_target(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=150.0,
                               clock=clock)
        per_second = pump(sampler, clock, 1200, 6.0, "steady")
        # 起步的前两秒允许有过冲（从 1.0 往目标靠），之后必须贴着 150
        for second, kept in enumerate(per_second[2:]):
            self.assertLess(abs(kept - 150), 60,
                            "第 %d 秒采样 %d，偏离目标过远" % (second + 3,
                                                           kept))

    def test_rate_settles_and_quits_moving(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 2000, 2.0, "settle")
        settled = sampler.rate()
        pump(sampler, clock, 2000, 2.0, "settle2")
        self.assertLess(abs(sampler.rate() - settled), 0.03)

    def test_below_target_traffic_is_fully_sampled(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=500.0,
                               clock=clock)
        per_second = pump(sampler, clock, 100, 4.0, "thin")
        for kept in per_second[1:]:
            self.assertEqual(kept, 100)
        self.assertEqual(sampler.rate(), 1.0)

    def test_small_throughput_wobble_does_not_swing_rate(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 2000, 2.0, "level")
        before = sampler.rate()
        # 在 ±5% 以内来回晃 4 秒，采样率不该一惊一乍
        for second in range(4):
            rate = 1900 if second % 2 == 0 else 2100
            pump(sampler, clock, rate, 1.0, "wobble-%d" % second)
        self.assertLess(abs(sampler.rate() - before), 0.06)


class TestBurstRecovery(unittest.TestCase):
    def test_rate_sinks_back_after_peak(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 4000, 3.0, "burst")
        low_after_burst = sampler.rate()
        self.assertLessEqual(low_after_burst, 0.1)
        per_second = pump(sampler, clock, 300, 6.0, "calm")
        # 恢复需要两三步，最后三秒必须沉回 200 附近
        for kept in per_second[-3:]:
            self.assertLess(abs(kept - 200), 60)
        self.assertGreater(sampler.rate(), 0.4)
        self.assertLess(sampler.rate(), 1.0)

    def test_rate_never_pinned_after_zero_samples(self):
        # 旧实现看到 sampled=0 会把采样率一把拽到 1.0 且钉住：
        # 极低 target 下压测“阈值一步到底”后再也回不来。
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=200.0,
                               clock=clock)
        pump(sampler, clock, 10000, 2.0, "flood")
        flood_rate = sampler.rate()
        self.assertLessEqual(flood_rate, 0.05)
        pump(sampler, clock, 20000, 2.0, "flood2")
        # 流量更高，采样率应继续贴地板，而不是跳回 1.0
        self.assertLess(sampler.rate(), flood_rate * 1.5)
        # 峰值过去流量回落到 target 以下（100 < 200），采样率应能
        # 回升到 1.0 而不是钉在地板（100 span/秒保证每 0.25 秒
        # 都有 tick，恢复有足够的控制步数）
        pump(sampler, clock, 100, 6.0, "drought")
        self.assertEqual(sampler.rate(), 1.0)


class TestStatsAndCounters(unittest.TestCase):
    def test_stats_counts_never_lose_or_double_count(self):
        clock = ManualClock()
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0,
                               clock=clock)
        pump(sampler, clock, 1000, 3.0, "acc")
        stats = sampler.stats()
        self.assertEqual(stats["total"], 3000)
        self.assertEqual(stats["sampled"] + stats["dropped"], 3000)
        self.assertGreater(stats["updates"], 0)

    def test_concurrent_stats_stay_coherent(self):
        sampler = TraceSampler(mode="adaptive", target_per_sec=100.0)
        workers = 8
        barrier = threading.Barrier(workers + 1)
        stop = []

        def worker():
            barrier.wait()
            index = 0
            while not stop:
                sampler.should_sample("t-%d" % (index // 3))
                index += 1

        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for _ in range(200):
            stats = sampler.stats()
            self.assertEqual(stats["sampled"] + stats["dropped"],
                             stats["total"])
        stop.append(True)
        for thread in threads:
            thread.join()


class TestDecisionCache(unittest.TestCase):
    def test_decision_is_made_once_and_reused(self):
        calls = []

        def decide(key):
            calls.append(key)
            return key.endswith("yes")

        cache = DecisionCache(decide, shards=4, generation_capacity=8,
                              generation_ttl=10.0)
        self.assertTrue(cache.get("a-yes"))
        self.assertTrue(cache.get("a-yes"))
        self.assertFalse(cache.get("b-no"))
        self.assertFalse(cache.get("b-no"))
        self.assertEqual(sorted(calls), ["a-yes", "b-no"])

    def test_capacity_rollover_keeps_recent_generation(self):
        clock = ManualClock()
        cache = DecisionCache(lambda key: True, shards=1,
                              generation_capacity=4, generation_ttl=100.0,
                              clock=clock)
        for key in ("a", "b", "c", "d"):
            cache.get(key)
        cache.get("e")  # 写满当代触发换代：a 掉出两代，e 在当代
        # 第一次换代：abcd 降为旧代，e 在当代，a 仍在缓存里
        self.assertEqual(len(cache), 5)
        cache.get("e")
        for key in ("f", "g", "h"):
            cache.get(key)
        cache.get("i")  # 第二次换代：abcd 彻底掉出两代
        self.assertEqual(len(cache), 5)
        # 旧条目 a 已不在缓存里，重新决策仍返回同一个 bool
        self.assertTrue(cache.get("a"))

    def test_ttl_rollover(self):
        clock = ManualClock()
        cache = DecisionCache(lambda key: True, shards=1,
                              generation_capacity=1000, generation_ttl=1.0,
                              clock=clock)
        cache.get("old")
        clock.advance(1.5)
        cache.get("new")  # 第一次换代：old 降入旧代，仍在缓存
        self.assertEqual(len(cache), 2)
        self.assertIn("old", cache._generations[0][1])
        clock.advance(1.5)
        cache.get("newer")  # 第二次换代：没人碰的 old 掉出两代
        self.assertEqual(len(cache), 2)
        current, previous = cache._generations[0]
        self.assertNotIn("old", current)
        self.assertNotIn("old", previous)

    def test_old_generation_hit_is_promoted(self):
        # 旧代里的活跃 trace 被访问时必须续命回当代，否则换代后
        # 采样率一变会把同一条 trace 的结论翻转。
        clock = ManualClock()
        cache = DecisionCache(lambda key: key == "hot", shards=1,
                              generation_capacity=1000, generation_ttl=1.0,
                              clock=clock)
        self.assertTrue(cache.get("hot"))
        clock.advance(1.5)
        cache.get("filler")  # 换代：hot 降入旧代
        self.assertIn("hot", cache._generations[0][1])
        self.assertTrue(cache.get("hot"))  # 旧代命中，应被带回当代
        self.assertIn("hot", cache._generations[0][0])
        clock.advance(1.5)
        cache.get("filler2")  # 再次换代：被续过命的 hot 仍然活着
        self.assertTrue(cache.get("hot"))


if __name__ == "__main__":
    unittest.main()
