"""保留策略、按住快照与回收可观测性的测试。

全部用假时钟驱动；为让小时/天桶边界干净，时钟初始值对齐整天。
"""

import unittest

from snapkeep.snapshots import RetentionPolicy, SnapshotStore


class FakeClock:
    """可手动推进的假时钟。"""

    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


DAY = RetentionPolicy.DAY_SECONDS
HOUR = RetentionPolicy.HOUR_SECONDS
DAY0 = 10 * DAY  # 对齐整天


def make_store(policy, t=DAY0, gc_interval=0.0):
    clock = FakeClock(t)
    store = SnapshotStore(
        clock=clock, retention=policy, gc_interval=gc_interval
    )
    return store, clock


class TestRetentionPolicy(unittest.TestCase):
    def test_rejects_bad_arguments(self):
        with self.assertRaises(ValueError):
            RetentionPolicy(-1, HOUR, 100)
        with self.assertRaises(ValueError):
            RetentionPolicy(HOUR, 60, 100)
        with self.assertRaises(ValueError):
            RetentionPolicy(60, HOUR, 0)

    def test_default_store_never_collects(self):
        clock = FakeClock(DAY0)
        store = SnapshotStore(clock=clock)
        for _ in range(5):
            store.take("dev", "x")
            clock.advance(DAY)
        self.assertEqual(len(store.list("dev")), 5)
        self.assertEqual(store.gc(), 0)
        self.assertEqual(store.gc_stats()["total_released"], 0)


class TestRecentWindow(unittest.TestCase):
    def test_window_boundary_is_inclusive(self):
        policy = RetentionPolicy(
            recent_seconds=100, hourly_seconds=1000, max_snapshots=1000
        )
        store, clock = make_store(policy)
        store.take("dev", "edge")  # 回收时恰好在 100 秒前
        clock.advance(100)
        store.take("dev", "now")
        self.assertEqual(store.gc(), 0)
        self.assertEqual(store.list("dev"), [DAY0, DAY0 + 100])

    def test_just_outside_window_goes_into_hourly_thinning(self):
        policy = RetentionPolicy(
            recent_seconds=100, hourly_seconds=10 * DAY, max_snapshots=1000
        )
        store, clock = make_store(policy, gc_interval=100 * DAY)
        store.take("dev", "a")
        clock.t += 100.5
        store.take("dev", "b")
        store.take("dev", "c")  # 同一小时桶内最后一张
        self.assertEqual(store.gc(), 1)
        self.assertEqual(
            store.list("dev"), [DAY0 + 100.5, DAY0 + 100.5]
        )


class TestHourlyThinning(unittest.TestCase):
    def test_keeps_last_snapshot_of_each_hour(self):
        policy = RetentionPolicy(
            recent_seconds=HOUR,
            hourly_seconds=3 * HOUR,
            max_snapshots=1000,
        )
        store, clock = make_store(policy, gc_interval=100 * DAY)
        # 两张落在第 0 小时，第 1、2 小时各一张。
        for minute in (10, 50, 70, 130):
            clock.t = DAY0 + minute * 60
            store.take("dev", f"m{minute}")
        clock.t = DAY0 + 3 * HOUR + 60  # 近窗只覆盖最后 1 小时
        store.gc()
        self.assertEqual(
            store.list("dev"),
            [
                DAY0 + 50 * 60,
                DAY0 + 70 * 60,
                DAY0 + 130 * 60,
            ],
        )

    def test_hourly_cut_boundary_is_inclusive(self):
        policy = RetentionPolicy(
            recent_seconds=HOUR,
            hourly_seconds=2 * HOUR,
            max_snapshots=1000,
        )
        store, clock = make_store(policy, gc_interval=100 * DAY)
        clock.t = DAY0 + 30 * 60  # 回收时恰好 age == 2h
        store.take("dev", "on-edge")
        clock.t = DAY0 + HOUR + 30 * 60
        store.take("dev", "hourly")
        clock.t = DAY0 + 2 * HOUR + 30 * 60
        store.gc()
        self.assertEqual(
            store.list("dev"),
            [DAY0 + 30 * 60, DAY0 + HOUR + 30 * 60],
        )


class TestDailyThinning(unittest.TestCase):
    def test_keeps_last_snapshot_of_each_day(self):
        policy = RetentionPolicy(
            recent_seconds=HOUR,
            hourly_seconds=DAY,
            max_snapshots=10000,
        )
        store, clock = make_store(policy, gc_interval=100 * DAY)
        specs = [
            (0 * DAY + 1 * HOUR, "d0-early"),
            (0 * DAY + 5 * HOUR, "d0-mid"),
            (1 * DAY + 2 * HOUR, "d1-early"),
            (1 * DAY + 8 * HOUR, "d1-last"),
            (2 * DAY + 9 * HOUR, "d2-last"),
        ]
        for dt, state in specs:
            clock.t = DAY0 + dt
            store.take("dev", state)
        clock.t = DAY0 + 3 * DAY + HOUR  # 第 0、1 天落在天档
        store.gc()
        self.assertEqual(
            store.list("dev"),
            [
                DAY0 + 5 * HOUR,
                DAY0 + 1 * DAY + 8 * HOUR,
                DAY0 + 2 * DAY + 9 * HOUR,
            ],
        )

    def test_hot_snapshot_protects_only_its_own_bucket(self):
        policy = RetentionPolicy(
            recent_seconds=30 * 60,
            hourly_seconds=DAY,
            max_snapshots=1000,
        )
        store, clock = make_store(policy)
        clock.t = DAY0 + HOUR - 20 * 60
        store.take("dev", "old-a")
        clock.t = DAY0 + HOUR - 5 * 60  # 旧小时桶最后一张
        store.take("dev", "old-b")
        clock.t = DAY0 + HOUR + 10 * 60  # 新桶且在近窗内
        store.take("dev", "hot")
        clock.t = DAY0 + HOUR + 40 * 60  # 旧桶整体退出近窗
        store.gc()
        self.assertEqual(
            store.list("dev"),
            [DAY0 + HOUR - 5 * 60, DAY0 + HOUR + 10 * 60],
        )


class TestMaxSnapshots(unittest.TestCase):
    def test_cap_drops_oldest_unpinned_first(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=100 * DAY, max_snapshots=2
        )
        store, clock = make_store(policy, gc_interval=100 * DAY)
        for hour in range(4):
            clock.t = DAY0 + hour * HOUR
            store.take("dev", f"h{hour}")
        self.assertEqual(store.gc(), 2)
        self.assertEqual(
            store.list("dev"),
            [DAY0 + 2 * HOUR, DAY0 + 3 * HOUR],
        )

    def test_pinned_snapshots_do_not_count_toward_cap(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=100 * DAY, max_snapshots=2
        )
        store, clock = make_store(policy, gc_interval=100 * DAY)
        for hour in range(4):
            clock.t = DAY0 + hour * HOUR
            store.take("dev", f"h{hour}")
        store.pin("dev", DAY0)  # 最旧一张被按住
        store.gc()
        self.assertEqual(
            store.list("dev"),
            [DAY0, DAY0 + 2 * HOUR, DAY0 + 3 * HOUR],
        )


class TestPins(unittest.TestCase):
    def test_pinned_snapshot_survives_all_tiers(self):
        policy = RetentionPolicy(
            recent_seconds=HOUR,
            hourly_seconds=DAY,
            max_snapshots=1000,
        )

        def build(pinned):
            store, clock = make_store(policy, gc_interval=100 * DAY)
            clock.t = DAY0 + 5 * 60
            store.take("dev", "incident")
            if pinned:
                store.pin("dev", clock.t)
            clock.t = DAY0 + 50 * 60
            store.take("dev", "same-hour-later")
            clock.t = DAY0 + 1 * DAY + 2 * HOUR
            store.take("dev", "next-day")
            clock.t = DAY0 + 10 * DAY
            store.gc()
            return store

        incident_ts = DAY0 + 5 * 60
        self.assertNotIn(incident_ts, build(pinned=False).list("dev"))
        pinned_store = build(pinned=True)
        self.assertIn(incident_ts, pinned_store.list("dev"))
        self.assertEqual(
            pinned_store.list("dev"),
            [
                DAY0 + 5 * 60,
                DAY0 + 50 * 60,
                DAY0 + 1 * DAY + 2 * HOUR,
            ],
        )
        self.assertEqual(pinned_store.get("dev", incident_ts), "incident")

    def test_pin_requires_existing_exact_timestamp(self):
        store, _clock = make_store(RetentionPolicy(1, 1, 10))
        store.take("dev", "x")
        with self.assertRaises(KeyError):
            store.pin("dev", DAY0 + 1)
        with self.assertRaises(KeyError):
            store.pin("ghost", DAY0)

    def test_unpin_allows_later_collection(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=0, max_snapshots=1
        )
        store, clock = make_store(policy)
        clock.t = DAY0
        store.take("dev", "a")
        store.pin("dev", DAY0)
        clock.t = DAY0 + HOUR
        store.take("dev", "b")
        store.gc()
        self.assertEqual(store.list("dev"), [DAY0, DAY0 + HOUR])
        store.unpin("dev", DAY0)
        store.gc()
        self.assertEqual(store.list("dev"), [DAY0 + HOUR])
        self.assertEqual(store.pins("dev"), [])
        self.assertEqual(store.pins("ghost"), [])

    def test_unpin_unknown_is_silent(self):
        store, _ = make_store(RetentionPolicy(1, 1, 10))
        store.unpin("dev", 123.0)  # 不报错


class TestAutoCollectionAndStats(unittest.TestCase):
    def test_take_triggers_collection_per_object(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=0, max_snapshots=1
        )
        store, clock = make_store(policy)
        store.take("a", 1)
        clock.advance(HOUR)
        store.take("a", 2)
        self.assertEqual(store.list("a"), [DAY0 + HOUR])

    def test_objects_are_gced_independently(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=0, max_snapshots=1
        )
        store, clock = make_store(policy)
        store.take("a", 1)
        clock.advance(HOUR)
        store.take("b", 1)
        self.assertEqual(store.list("a"), [DAY0])
        self.assertEqual(store.list("b"), [DAY0 + HOUR])

    def test_gc_interval_throttles_take_path(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=0, max_snapshots=1
        )
        store, clock = make_store(policy, gc_interval=HOUR)
        store.take("dev", "a")
        clock.advance(10)
        store.take("dev", "b")  # 距上次回收不足 1 小时，跳过
        self.assertEqual(store.list("dev"), [DAY0, DAY0 + 10])
        clock.advance(HOUR)
        store.take("dev", "c")  # 间隔到，触发回收
        self.assertEqual(store.list("dev"), [DAY0 + HOUR + 10])

    def test_manual_gc_bypasses_interval(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=0, max_snapshots=1
        )
        store, clock = make_store(policy, gc_interval=10 * DAY)
        store.take("dev", "a")
        clock.advance(10)
        store.take("dev", "b")
        self.assertEqual(len(store.list("dev")), 2)
        self.assertEqual(store.gc("dev"), 1)
        self.assertEqual(store.list("dev"), [DAY0 + 10])

    def test_gc_all_sweeps_every_object(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=0, max_snapshots=1
        )
        store, clock = make_store(policy, gc_interval=10 * DAY)
        store.take("a", 1)
        clock.advance(10)
        store.take("a", 2)  # 节流期内，a 攒到两条
        clock.advance(HOUR - 10)
        store.take("b", 1)
        released = store.gc()
        self.assertEqual(released, 1)
        self.assertEqual(store.list("a"), [DAY0 + 10])
        self.assertEqual(store.list("b"), [DAY0 + HOUR])

    def test_stats_track_runs_release_and_last_run_time(self):
        policy = RetentionPolicy(
            recent_seconds=0, hourly_seconds=100 * DAY, max_snapshots=2
        )
        store, clock = make_store(policy)
        self.assertEqual(
            store.gc_stats(),
            {
                "gc_runs": 0,
                "last_released": 0,
                "total_released": 0,
                "last_run_at": None,
            },
        )
        store.take("dev", "a")
        clock.advance(HOUR)
        store.take("dev", "b")
        clock.advance(HOUR)
        store.take("dev", "c")  # 自动回收一轮，释放 1 条
        stats = store.gc_stats()
        self.assertEqual(stats["gc_runs"], 3)
        self.assertEqual(stats["last_released"], 1)
        self.assertEqual(stats["total_released"], 1)
        self.assertEqual(stats["last_run_at"], DAY0 + 2 * HOUR)
        clock.advance(HOUR)
        store.take("dev", "d")  # 又释放 1 条，累计 2
        stats = store.gc_stats()
        self.assertEqual(stats["gc_runs"], 4)
        self.assertEqual(stats["last_released"], 1)
        self.assertEqual(stats["total_released"], 2)
        self.assertEqual(stats["last_run_at"], DAY0 + 3 * HOUR)


if __name__ == "__main__":
    unittest.main()
