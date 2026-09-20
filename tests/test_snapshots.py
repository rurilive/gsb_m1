"""SnapshotStore 现有行为的锁定测试。"""

import unittest

from snapkeep.snapshots import SnapshotStore


class FakeClock:
    """可手动推进的假时钟。"""

    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestSnapshotStore(unittest.TestCase):
    def test_take_returns_timestamp_and_get_reads_it(self):
        clock = FakeClock(100.0)
        s = SnapshotStore(clock=clock)
        ts = s.take("dev", "v1")
        self.assertEqual(ts, 100.0)
        self.assertEqual(s.get("dev", 100.0), "v1")

    def test_get_returns_latest_not_after_ts(self):
        clock = FakeClock(0.0)
        s = SnapshotStore(clock=clock)
        s.take("dev", "v1")
        clock.advance(10)
        s.take("dev", "v2")
        clock.advance(10)
        s.take("dev", "v3")
        self.assertEqual(s.get("dev", 5), "v1")
        self.assertEqual(s.get("dev", 10), "v2")
        self.assertEqual(s.get("dev", 15), "v2")
        self.assertEqual(s.get("dev", 25), "v3")

    def test_get_before_first_snapshot_returns_none(self):
        clock = FakeClock(50.0)
        s = SnapshotStore(clock=clock)
        s.take("dev", "v1")
        self.assertIsNone(s.get("dev", 49.9))

    def test_get_unknown_object_returns_none(self):
        s = SnapshotStore(clock=FakeClock())
        self.assertIsNone(s.get("nope", 1000.0))

    def test_list_is_ascending_timestamps(self):
        clock = FakeClock(0.0)
        s = SnapshotStore(clock=clock)
        for _ in range(3):
            s.take("dev", "x")
            clock.advance(7)
        self.assertEqual(s.list("dev"), [0.0, 7.0, 14.0])

    def test_list_unknown_object_is_empty(self):
        s = SnapshotStore(clock=FakeClock())
        self.assertEqual(s.list("nope"), [])

    def test_list_returns_fresh_list(self):
        clock = FakeClock(0.0)
        s = SnapshotStore(clock=clock)
        s.take("dev", "v1")
        out = s.list("dev")
        out.append(999.0)
        self.assertEqual(s.list("dev"), [0.0])

    def test_objects_are_independent(self):
        clock = FakeClock(0.0)
        s = SnapshotStore(clock=clock)
        s.take("a", 1)
        clock.advance(5)
        s.take("b", 2)
        self.assertEqual(s.get("a", 5), 1)
        self.assertEqual(s.get("b", 5), 2)
        self.assertEqual(s.list("a"), [0.0])

    def test_states_can_be_repeated(self):
        clock = FakeClock(0.0)
        s = SnapshotStore(clock=clock)
        s.take("dev", "same")
        clock.advance(1)
        s.take("dev", "same")
        self.assertEqual(s.list("dev"), [0.0, 1.0])
        self.assertEqual(s.get("dev", 1.0), "same")

    def test_clock_is_injectable(self):
        s = SnapshotStore(clock=lambda: 42.0)
        self.assertEqual(s.take("dev", "v"), 42.0)


if __name__ == "__main__":
    unittest.main()
