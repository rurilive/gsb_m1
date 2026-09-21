"""持久化防回归测试：next_run 时区、paused 状态。"""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scheduler import DailyTrigger, Store, Task


class StoreRoundtripTest(unittest.TestCase):
    """现象 5：重启后 next_run 偏 8 小时、paused 丢失。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "tasks.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_next_run_instant_preserved(self):
        store = Store()
        moment = datetime(2026, 3, 1, 1, 30, tzinfo=timezone.utc)  # 香港墙钟 09:30
        tasks = {"a": Task("a", DailyTrigger(9, 30), lambda: None, moment)}
        store.save(self.path, tasks)
        loaded = store.load(self.path)
        self.assertEqual(loaded["a"].next_run, moment)

    def test_paused_preserved(self):
        store = Store()
        moment = datetime(2026, 3, 1, 1, 30, tzinfo=timezone.utc)
        tasks = {
            "paused-task": Task("paused-task", DailyTrigger(9, 30), lambda: None,
                                moment, paused=True),
            "active-task": Task("active-task", DailyTrigger(9, 30), lambda: None, moment),
        }
        store.save(self.path, tasks)
        loaded = store.load(self.path)
        self.assertTrue(loaded["paused-task"].paused)
        self.assertFalse(loaded["active-task"].paused)

    def test_trigger_preserved(self):
        store = Store()
        moment = datetime(2026, 3, 1, 1, 30, tzinfo=timezone.utc)
        tasks = {"a": Task("a", DailyTrigger(9, 30, tz="Europe/Berlin"), lambda: None, moment)}
        store.save(self.path, tasks)
        loaded = store.load(self.path)
        self.assertEqual(str(loaded["a"].trigger.tz), "Europe/Berlin")
        self.assertEqual((loaded["a"].trigger.hour, loaded["a"].trigger.minute), (9, 30))


if __name__ == "__main__":
    unittest.main()
