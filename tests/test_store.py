"""持久化回归测试：next_run 的 UTC 往返、paused 恢复、旧格式兼容。"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scheduler import DailyTrigger, FakeClock, IntervalTrigger, Scheduler, Store
from scheduler.scheduler import Task

HKT = ZoneInfo("Asia/Hong_Kong")


class StoreTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.path = self.tmp.name
        self.tmp.close()
        self.addCleanup(lambda: Path(self.path).unlink(missing_ok=True))

    def _scheduler(self):
        return Scheduler(FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc)))

    def test_next_run_roundtrip_no_eight_hour_shift(self):
        nxt = datetime(2026, 2, 1, 8, 0, tzinfo=HKT).astimezone(timezone.utc)
        sched = self._scheduler()
        sched._tasks["p"] = Task("p", DailyTrigger(8, 0), lambda: None, nxt)
        sched.save(self.path)
        loaded = Store().load(self.path)["p"]
        self.assertEqual(loaded.next_run, nxt)

    def test_paused_state_persisted(self):
        nxt = datetime(2026, 2, 1, tzinfo=timezone.utc)
        sched = self._scheduler()
        sched._tasks["p"] = Task("p", IntervalTrigger(timedelta(minutes=1)),
                                 lambda: None, nxt, paused=True)
        sched.save(self.path)
        loaded = Store().load(self.path)["p"]
        self.assertTrue(loaded.paused)

    def test_restart_keeps_paused_and_schedule(self):
        # 端到端：save -> load 进新调度器，暂停的任务到点不得执行，next_run 不偏移。
        clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        sched = Scheduler(clock, worker_count=1, tick=0.05, misfire_grace=2.0)
        fired = []
        sched.add("p", IntervalTrigger(timedelta(seconds=10)), lambda: fired.append(1))
        sched.pause("p")
        saved_next = sched.get("p").next_run
        sched.save(self.path)

        clock2 = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        sched2 = Scheduler(clock2, worker_count=1, tick=0.05, misfire_grace=2.0)
        sched2.load(self.path)
        sched2.start()
        try:
            clock2.advance(60)
            self.assertTrue(sched2.wait_idle(5.0))
            self.assertEqual(fired, [])
            self.assertTrue(sched2.get("p").paused)
            self.assertEqual(sched2.get("p").next_run, saved_next)
        finally:
            sched2.stop()

    def test_legacy_naive_local_snapshot_compat(self):
        # 旧版把香港墙钟剥掉 tzinfo 存储，加载时必须按香港时区解释，不能当 UTC。
        legacy = [{
            "id": "p",
            "trigger": {"kind": "DailyTrigger", "hour": 8, "minute": 0,
                        "tz": "Asia/Shanghai"},
            "next_run": "2026-02-01T08:00:00",
        }]
        Path(self.path).write_text(json.dumps(legacy))
        loaded = Store().load(self.path)["p"]
        self.assertEqual(loaded.next_run,
                         datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
