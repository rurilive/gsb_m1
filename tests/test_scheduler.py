"""调度器防回归测试：misfire/补跑风暴、删除暂停失效、持久化恢复。"""
import queue
import tempfile
import threading
import unittest
from time import sleep as real_sleep
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scheduler import FakeClock, IntervalTrigger, Scheduler

UTC = timezone.utc


def drain(sched: Scheduler) -> list:
    """取出当前已入队但尚未执行的 (task_id, generation)。"""
    items = []
    while True:
        try:
            items.append(sched._queue.get_nowait())
        except queue.Empty:
            break
    return items


def collect(sched: Scheduler, now: datetime) -> None:
    with sched._lock:
        sched._collect_due_locked(now)


def start_worker(sched: Scheduler):
    t = threading.Thread(target=sched._worker, daemon=True)
    t.start()
    return t


def stop_worker(sched: Scheduler, t) -> None:
    sched._stopping = True
    t.join(timeout=2.0)
    sched._stopping = False


def run_one_worker_cycle(sched: Scheduler) -> None:
    """消费当前队列里的真实任务（调用前完成 remove/pause，模拟 worker 滞后取队）。"""
    stop_worker(sched, start_worker(sched))


class MisfireTest(unittest.TestCase):
    # 现象 3：时钟前跳后，远超宽限期的任务不能补跑；仅晚一两分钟的要正常执行。

    def _make(self, grace: float = 60.0):
        clock = FakeClock(datetime(2026, 6, 1, 12, 0, tzinfo=UTC))
        sched = Scheduler(clock, worker_count=0, tick=3600, misfire_grace=grace)
        anchor = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
        sched.add("t", IntervalTrigger(timedelta(minutes=10), anchor=anchor),
                  lambda: None)
        return clock, sched

    def test_slightly_late_still_fires(self):
        _, sched = self._make(grace=120.0)
        # next_run = 12:10；晚 90 秒，落在 120 秒宽限期内，应执行一次。
        collect(sched, datetime(2026, 6, 1, 12, 11, 30, tzinfo=UTC))
        self.assertEqual([tid for tid, _ in drain(sched)], ["t"])
        # 合并错过的网格：next_run 推进到 now 之后的第一个锚点，不会补跑。
        self.assertEqual(sched.get("t").next_run,
                         datetime(2026, 6, 1, 12, 20, tzinfo=UTC))

    def test_way_overdue_is_skipped_without_catchup_storm(self):
        _, sched = self._make(grace=60.0)
        # 时钟从 12:00 前跳到 18:00：错过 35 个锚点，全部超出 60 秒宽限。
        collect(sched, datetime(2026, 6, 1, 18, 0, tzinfo=UTC))
        self.assertEqual(drain(sched), [])
        self.assertEqual(sched.get("t").next_run,
                         datetime(2026, 6, 1, 18, 10, tzinfo=UTC))

    def test_repeated_ticks_after_big_jump_do_not_burst(self):
        # 模拟 worker 持续消费、_loop 在同一时刻反复 tick：
        # 旧代码每个 tick 只追一个历史锚点，会持续补跑；新代码一步滚到未来。
        _, sched = self._make(grace=60.0)
        jump = datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
        fired = 0
        for _ in range(40):
            collect(sched, jump)
            fired += len(drain(sched))
            sched._inflight.clear()
        self.assertEqual(fired, 0)
        self.assertEqual(sched.get("t").next_run,
                         datetime(2026, 6, 1, 18, 10, tzinfo=UTC))


class StaleGenerationTest(unittest.TestCase):
    # 现象 2：任务删除后，已经在队列里的触发不得再执行。

    def test_removed_task_is_not_executed(self):
        ran = []
        clock = FakeClock(datetime(2026, 6, 1, 12, 0, tzinfo=UTC))
        sched = Scheduler(clock, worker_count=0, misfire_grace=60.0)
        anchor = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
        sched.add("t", IntervalTrigger(timedelta(minutes=10), anchor=anchor),
                  lambda: ran.append("t"))
        collect(sched, datetime(2026, 6, 1, 12, 10, 0, tzinfo=UTC))
        sched.remove("t")  # 在 worker 取走之前删除
        run_one_worker_cycle(sched)
        self.assertEqual(ran, [])

    def test_paused_task_is_not_executed_and_resumes_safely(self):
        ran = []
        clock = FakeClock(datetime(2026, 6, 1, 12, 0, tzinfo=UTC))
        sched = Scheduler(clock, worker_count=0, misfire_grace=60.0)
        anchor = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
        sched.add("t", IntervalTrigger(timedelta(minutes=10), anchor=anchor),
                  lambda: ran.append("t"))
        collect(sched, datetime(2026, 6, 1, 12, 10, 0, tzinfo=UTC))
        sched.pause("t")
        run_one_worker_cycle(sched)
        self.assertEqual(ran, [])
        sched.resume("t")
        # 恢复后新的到期触发仍可正常执行。
        collect(sched, datetime(2026, 6, 1, 12, 20, 0, tzinfo=UTC))
        run_one_worker_cycle(sched)
        self.assertEqual(ran, ["t"])

    def test_re_added_task_is_not_confused_with_stale_entry(self):
        ran_old, ran_new = [], []
        clock = FakeClock(datetime(2026, 6, 1, 12, 10, tzinfo=UTC))
        sched = Scheduler(clock, worker_count=0, misfire_grace=60.0)
        anchor = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
        trig = IntervalTrigger(timedelta(minutes=10), anchor=anchor)
        sched.add("t", trig, lambda: ran_old.append("old"))
        collect(sched, datetime(2026, 6, 1, 12, 10, tzinfo=UTC))
        sched.remove("t")
        sched.add("t", trig, lambda: ran_new.append("new"))
        run_one_worker_cycle(sched)  # 旧队列项不应触发任何一个回调
        self.assertEqual((ran_old, ran_new), ([], []))


class PersistenceTest(unittest.TestCase):
    # 现象 5：重启后 paused 状态保持；next_run 不能整体偏 8 小时。

    def test_roundtrip_preserves_utc_and_paused(self):
        clock = FakeClock(datetime(2026, 6, 1, 12, 0, tzinfo=UTC))
        sched = Scheduler(clock, worker_count=0)
        anchor = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
        sched.add("running", IntervalTrigger(timedelta(minutes=10), anchor=anchor),
                  lambda: None)
        sched.add("paused-job", IntervalTrigger(timedelta(minutes=5), anchor=anchor),
                  lambda: None, paused=True)
        expected_run = sched.get("running").next_run
        expected_paused = sched.get("paused-job").next_run

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "tasks.json")
            sched.save(path)
            restored = Scheduler(FakeClock(clock.now()), worker_count=0)
            restored.load(path)

        self.assertEqual(restored.get("running").next_run, expected_run)
        self.assertEqual(restored.get("running").next_run.tzinfo, UTC)
        self.assertFalse(restored.get("running").paused)
        self.assertEqual(restored.get("paused-job").next_run, expected_paused)
        self.assertTrue(restored.get("paused-job").paused)

    def test_legacy_naive_hongkong_snapshot_is_recovered_without_shift(self):
        # 旧版本把 UTC 时刻以香港墙钟裸时间落盘，加载时必须按香港时区解读。
        payload = (
            '[{"id": "legacy", '
            '"trigger": {"kind": "IntervalTrigger", "interval": 600.0, '
            '"anchor": "2026-01-01T00:00:00+00:00"}, '
            '"next_run": "2026-06-01T20:00:00"}]'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.json"
            path.write_text(payload)
            sched = Scheduler(FakeClock(datetime(2026, 6, 1, tzinfo=UTC)),
                              worker_count=0)
            sched.load(str(path))
        self.assertEqual(sched.get("legacy").next_run,
                         datetime(2026, 6, 1, 12, 0, tzinfo=UTC))


class EndToEndLoopTest(unittest.TestCase):
    """用 FakeClock 驱动真实 _loop + worker，验证线程级集成行为。"""

    def test_fires_on_schedule_and_skips_paused(self):
        ran = []
        clock = FakeClock(datetime(2026, 6, 1, 12, 0, tzinfo=UTC))
        sched = Scheduler(clock, worker_count=1, tick=0.01, misfire_grace=5.0)
        anchor = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
        sched.add("a", IntervalTrigger(timedelta(seconds=10), anchor=anchor),
                  lambda: ran.append("a"))
        sched.add("b", IntervalTrigger(timedelta(seconds=10), anchor=anchor),
                  lambda: ran.append("b"), paused=True)
        sched.start()
        try:
            for _ in range(5):
                clock.advance(5)
                real_sleep(0.05)  # 让真实 _loop 线程跑到推进后的时刻
            self.assertTrue(sched.wait_idle(3.0))
        finally:
            sched.stop()
        self.assertGreaterEqual(ran.count("a"), 2)
        self.assertEqual(ran.count("b"), 0)


if __name__ == "__main__":
    unittest.main()
