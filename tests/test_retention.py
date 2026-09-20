"""保留策略与回收的测试：假时钟钉死分档窗口与抽稀边界。"""

import unittest

from snapkeep.snapshots import RetentionPolicy, SnapshotStore


class FakeClock:
    """可手动推进/跳转的假时钟。"""

    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def make_store(clock, **policy_kw):
    """gc_interval 拉得极大，保证测试里只有 collect_now 会触发回收。"""
    policy = RetentionPolicy(**policy_kw)
    return SnapshotStore(clock=clock, retention=policy, gc_interval=1e18)


def take_at(store, clock, obj, ts):
    clock.t = float(ts)
    return store.take(obj, f"v{ts}")


class TestTieredThinning(unittest.TestCase):
    """三档保留：recent 全留，小时档留每小时最后一张，天档留每天最后一张。"""

    def setUp(self):
        self.clock = FakeClock()
        # recent 1 小时，hourly 3 小时；now=360000（第 100 小时）
        # recent_cut=356400, hourly_cut=349200
        self.store = make_store(
            self.clock, recent_window=3600, hourly_window=3 * 3600
        )

    def fill(self):
        for ts in (100, 200, 87000, 88000, 349300, 349400, 353000, 357000, 358000):
            take_at(self.store, self.clock, "dev", ts)
        self.clock.t = 360000.0

    def test_tiered_thinning(self):
        self.fill()
        self.store.collect_now()
        # 天档（<349200）：day0 留 200，day1 留 88000
        # 小时档 [349200,356400)：hour97 留 349400，hour98 留 353000
        # recent（>=356400）：357000、358000 全留
        self.assertEqual(
            self.store.list("dev"),
            [200.0, 88000.0, 349400.0, 353000.0, 357000.0, 358000.0],
        )

    def test_get_after_gc_reads_thinned_timeline(self):
        self.fill()
        self.store.collect_now()
        self.assertEqual(self.store.get("dev", 350000.0), "v349400")
        self.assertEqual(self.store.get("dev", 359000.0), "v358000")
        self.assertIsNone(self.store.get("dev", 199.0))

    def test_objects_are_collected_independently(self):
        self.fill()
        take_at(self.store, self.clock, "other", 100)
        take_at(self.store, self.clock, "other", 359000)
        self.clock.t = 360000.0
        self.store.collect_now()
        # 100 是 other 当天（day0）最后一张，按天档规则保留
        self.assertEqual(self.store.list("other"), [100.0, 359000.0])
        self.assertEqual(len(self.store.list("dev")), 6)


class TestZoneBoundaries(unittest.TestCase):
    """边界时刻归入较新的一档。"""

    def test_boundary_belongs_to_newer_tier(self):
        clock = FakeClock()
        store = make_store(clock, recent_window=1000, hourly_window=2000)
        # now=10000：recent_cut=9000，hourly_cut=8000
        take_at(store, clock, "dev", 100)      # 天档 day0
        take_at(store, clock, "dev", 7999.99)  # 天档 day0（age>2000）
        take_at(store, clock, "dev", 8000)     # 恰在 hourly_cut：小时档 hour2
        take_at(store, clock, "dev", 8100)     # 小时档 hour2
        take_at(store, clock, "dev", 9000)     # 恰在 recent_cut：recent
        take_at(store, clock, "dev", 9100)     # recent
        clock.t = 10000.0
        store.collect_now()
        # day0 只留 7999.99；hour2 只留 8100；recent 两张全留
        self.assertEqual(
            store.list("dev"), [7999.99, 8100.0, 9000.0, 9100.0]
        )


class TestMaxPerObjCap(unittest.TestCase):
    def test_cap_drops_oldest_after_thinning(self):
        clock = FakeClock()
        store = make_store(
            clock, recent_window=1000, hourly_window=2000, max_per_obj=3
        )
        for ts in (9000, 9100, 9200, 9300, 9400):  # 全在 recent 档
            take_at(store, clock, "dev", ts)
        clock.t = 10000.0
        store.collect_now()
        self.assertEqual(store.list("dev"), [9200.0, 9300.0, 9400.0])

    def test_cap_skips_pinned(self):
        clock = FakeClock()
        store = make_store(
            clock, recent_window=1000, hourly_window=2000, max_per_obj=3
        )
        for ts in (9000, 9100, 9200, 9300, 9400):
            take_at(store, clock, "dev", ts)
        store.pin("dev", 9000.0)
        clock.t = 10000.0
        store.collect_now()
        # 超 2 条，从最旧的非 pin 丢：9100、9200 出局，pin 住的 9000 留下
        self.assertEqual(store.list("dev"), [9000.0, 9300.0, 9400.0])


class TestPin(unittest.TestCase):
    def test_pin_survives_thinning(self):
        clock = FakeClock()
        store = make_store(clock, recent_window=3600, hourly_window=3 * 3600)
        take_at(store, clock, "dev", 100)
        take_at(store, clock, "dev", 200)
        store.pin("dev", 100.0)
        clock.t = 360000.0
        store.collect_now()
        self.assertEqual(store.list("dev"), [100.0, 200.0])
        self.assertEqual(store.get("dev", 150.0), "v100")

    def test_unpin_lets_gc_collect(self):
        clock = FakeClock()
        store = make_store(clock, recent_window=3600, hourly_window=3 * 3600)
        take_at(store, clock, "dev", 100)
        take_at(store, clock, "dev", 200)
        store.pin("dev", 100.0)
        clock.t = 360000.0
        store.collect_now()
        store.unpin("dev", 100.0)
        store.collect_now()
        self.assertEqual(store.list("dev"), [200.0])


class TestGcTriggerAndStats(unittest.TestCase):
    def test_take_triggers_gc_no_more_than_once_per_interval(self):
        clock = FakeClock()
        policy = RetentionPolicy(recent_window=10, hourly_window=20)
        store = SnapshotStore(clock=clock, retention=policy, gc_interval=100)
        take_at(store, clock, "dev", 0)    # 首次写入建立回收基线
        take_at(store, clock, "dev", 5)    # 距上次回收 <100，不扫
        take_at(store, clock, "dev", 10)   # 同上
        self.assertEqual(store.gc_stats()["runs"], 1)
        self.assertEqual(store.list("dev"), [0.0, 5.0, 10.0])  # 还没回收
        take_at(store, clock, "dev", 110)  # 间隔够 100，触发一轮
        stats = store.gc_stats()
        self.assertEqual(stats["runs"], 2)
        # now=110：0/5/10 都在天档 day0，只留最后的 10；110 在 recent
        self.assertEqual(store.list("dev"), [10.0, 110.0])

    def test_stats_report_released_counts_and_last_run(self):
        clock = FakeClock()
        store = make_store(clock, recent_window=3600, hourly_window=3 * 3600)
        for ts in (100, 200, 87000, 88000, 349300, 349400, 353000, 357000, 358000):
            take_at(store, clock, "dev", ts)
        clock.t = 360000.0
        released = store.collect_now()
        self.assertEqual(released, 3)
        stats = store.gc_stats()
        self.assertEqual(stats["last_run"], 360000.0)
        self.assertEqual(stats["last_released"], 3)
        self.assertEqual(stats["total_released"], 3)
        self.assertGreaterEqual(stats["runs"], 1)

    def test_no_retention_no_gc(self):
        clock = FakeClock()
        store = SnapshotStore(clock=clock)
        take_at(store, clock, "dev", 0)
        take_at(store, clock, "dev", 10**9)
        self.assertEqual(store.collect_now(), 0)
        self.assertEqual(store.gc_stats()["runs"], 0)
        self.assertEqual(store.list("dev"), [0.0, 1e9])


class TestPolicyValidation(unittest.TestCase):
    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            RetentionPolicy(recent_window=0, hourly_window=10)
        with self.assertRaises(ValueError):
            RetentionPolicy(recent_window=100, hourly_window=10)
        with self.assertRaises(ValueError):
            RetentionPolicy(recent_window=10, hourly_window=100, max_per_obj=0)


if __name__ == "__main__":
    unittest.main()
