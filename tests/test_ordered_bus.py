"""OrderedBus 顺序编号、重放、背压、重启与压力的测试。"""

import os
import random
import tempfile
import threading
import time
import unittest

from eventwire.bus import OrderedBus, SyncBus, WindowExpired
from eventwire.journal import Journal


class OrderedBusCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "events.jsonl")

    def open_bus(self, **kwargs):
        bus = OrderedBus(self.path, **kwargs)
        self.addCleanup(bus.close)
        return bus

    def journal_records(self):
        with Journal(self.path) as journal:
            return journal.read()

    @staticmethod
    def recorder(seen, name):
        def handler(topic, payload):
            seen[name].append((topic, payload["step"]))
        return handler


class TestSeq(OrderedBusCase):
    def test_publish_assigns_monotonic_seq_and_persists(self):
        bus = self.open_bus()
        seqs = [bus.publish("order.paid", {"n": n}) for n in range(3)]
        self.assertEqual(seqs, [1, 2, 3])
        records = self.journal_records()
        self.assertEqual([r["seq"] for r in records], [1, 2, 3])
        self.assertEqual(records[0]["topic"], "order.paid")
        self.assertEqual(records[0]["payload"], {"n": 0})

    def test_duplicate_seq_dropped_idempotently(self):
        bus = self.open_bus()
        seen = []
        bus.subscribe("audit", lambda t, p: seen.append(p))
        first = bus.publish("order.paid", {"n": 1})
        again = bus.publish("order.paid", {"n": 1}, seq=first)
        self.assertEqual(again, first)
        self.assertTrue(bus.flush(timeout=5))
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(self.journal_records()), 1)

    def test_explicit_future_seq_then_auto_continues(self):
        bus = self.open_bus()
        self.assertEqual(bus.publish("tick", 1, seq=10), 10)
        self.assertEqual(bus.publish("tick", 2), 11)

    def test_invalid_arguments(self):
        bus = self.open_bus()
        with self.assertRaises(ValueError):
            bus.publish("a..b", 1)
        with self.assertRaises(ValueError):
            bus.publish("a.*", 1)
        with self.assertRaises(ValueError):
            bus.publish("tick", 1, seq=0)
        with self.assertRaises(ValueError):
            bus.publish("tick", 1, seq="3")
        with self.assertRaises(ValueError):
            OrderedBus(self.path, window=0)
        with self.assertRaises(ValueError):
            OrderedBus(self.path, backlog=0)
        with self.assertRaises(ValueError):
            OrderedBus(self.path, overflow="explode")
        with self.assertRaises(ValueError):
            bus.subscribe("", lambda t, p: None)
        with self.assertRaises(TypeError):
            bus.subscribe("a", "not-callable")
        with self.assertRaises(ValueError):
            bus.subscribe("a", lambda t, p: None, since=-1)

    def test_close_then_publish_raises(self):
        bus = self.open_bus()
        bus.close()
        bus.close()  # 重复关不报错
        with self.assertRaises(ValueError):
            bus.publish("tick", 1)


class TestReplay(OrderedBusCase):
    def test_since_replays_window_in_order(self):
        bus = self.open_bus()
        for n in range(1, 6):
            bus.publish("tick", {"n": n})
        seen = []
        bus.subscribe("late", lambda t, p: seen.append(p["n"]), since=2)
        # 补发是同步的，subscribe 返回时已经到齐
        self.assertEqual(seen, [3, 4, 5])

    def test_since_respects_pattern(self):
        bus = self.open_bus()
        bus.publish("order.paid", 1)
        bus.publish("user.created", 2)
        seen = []
        bus.subscribe("late", lambda t, p: seen.append(t), "order.**", since=0)
        self.assertEqual(seen, ["order.paid"])

    def test_since_none_means_live_only(self):
        bus = self.open_bus()
        bus.publish("tick", 1)
        seen = []
        bus.subscribe("live", lambda t, p: seen.append(p))
        bus.publish("tick", 2)
        self.assertTrue(bus.flush(timeout=5))
        self.assertEqual(seen, [2])

    def test_window_expired_raises_not_skips(self):
        bus = self.open_bus(window=4)
        for n in range(10):
            bus.publish("tick", n)
        with self.assertRaises(WindowExpired):
            bus.subscribe("ancient", lambda t, p: None, since=3)
        seen = []
        bus.subscribe("recent", lambda t, p: seen.append(p), since=6)
        self.assertEqual(seen, [6, 7, 8, 9])

    def test_resubscribe_returns_flag_and_replaces(self):
        bus = self.open_bus()
        self.assertTrue(bus.subscribe("a", lambda t, p: None))
        self.assertFalse(bus.subscribe("a", lambda t, p: None))
        self.assertEqual(bus.subscriber_names(), ("a",))
        self.assertTrue(bus.unsubscribe("a"))
        self.assertFalse(bus.unsubscribe("a"))


class TestBackpressure(OrderedBusCase):
    def test_slow_subscriber_does_not_block_others(self):
        bus = self.open_bus()
        entered = threading.Event()
        gate = threading.Event()

        def slow(topic, payload):
            entered.set()
            gate.wait(5)

        fast_seen = []
        bus.subscribe("slow", slow)
        bus.subscribe("fast", lambda t, p: fast_seen.append(p))
        started = time.perf_counter()
        bus.publish("tick", 1)
        self.assertTrue(entered.wait(5))  # slow 的投递线程已经卡住
        deadline = time.monotonic() + 5
        while not fast_seen and time.monotonic() < deadline:
            time.sleep(0.005)
        gate.set()
        self.assertEqual(fast_seen, [1])
        self.assertLess(time.perf_counter() - started, 2)

    def test_drop_overflow_counts_and_bounds_backlog(self):
        bus = self.open_bus(backlog=2, overflow="drop")
        entered = threading.Event()
        gate = threading.Event()
        received = []

        def slow(topic, payload):
            entered.set()
            gate.wait(5)
            received.append(payload)

        bus.subscribe("slow", slow)
        bus.publish("tick", 0)
        self.assertTrue(entered.wait(5))  # 第一条占住处理器
        for n in range(1, 7):
            bus.publish("tick", n)
        stats = bus.stats()["subscribers"]["slow"]
        self.assertEqual(stats["dropped"], 4)  # 队列只留得下 2 条
        self.assertLessEqual(stats["pending"], 2)
        gate.set()
        self.assertTrue(bus.flush(timeout=5))
        self.assertEqual(len(received), 3)

    def test_disconnect_overflow(self):
        bus = self.open_bus(backlog=1, overflow="disconnect")
        entered = threading.Event()
        gate = threading.Event()

        def slow(topic, payload):
            entered.set()
            gate.wait(5)

        bus.subscribe("slow", slow)
        bus.publish("tick", 0)
        self.assertTrue(entered.wait(5))
        bus.publish("tick", 1)  # 占满队列
        bus.publish("tick", 2)  # 超限，断开
        bus.publish("tick", 3)  # 已断开，只计数
        stats = bus.stats()["subscribers"]["slow"]
        self.assertEqual(stats["state"], "disconnected")
        self.assertEqual(stats["dropped"], 2)
        gate.set()


class TestRestart(OrderedBusCase):
    def test_restart_continues_numbering_no_resend_no_gap(self):
        bus = self.open_bus()
        for n in range(3):
            bus.publish("tick", {"n": n})
        bus.close()
        reopened = self.open_bus()
        self.assertEqual(reopened.stats()["high_water"], 3)
        self.assertEqual(reopened.publish("tick", {"n": 3}), 4)
        seqs = [r["seq"] for r in self.journal_records()]
        self.assertEqual(seqs, [1, 2, 3, 4])

    def test_restart_replays_from_journal_window(self):
        bus = self.open_bus(window=3)
        for n in range(5):
            bus.publish("tick", n)
        bus.close()
        reopened = self.open_bus(window=3)
        seen = []
        reopened.subscribe("late", lambda t, p: seen.append(p), since=2)
        self.assertEqual(seen, [2, 3, 4])
        with self.assertRaises(WindowExpired):
            reopened.subscribe("ancient", lambda t, p: None, since=0)


class TestStress(OrderedBusCase):
    def test_multithreaded_publish_no_dup_no_gap(self):
        # 积压上限给得比总量大，压测只验编号不重不漏、投递不丢；
        # 超限丢弃的口径在 TestBackpressure 里验
        bus = self.open_bus(backlog=1024)
        received = []
        bus.subscribe("all", lambda t, p: received.append((p["tid"], p["n"])))
        threads_n, per = 4, 50
        seqs = []

        def work(tid):
            for n in range(per):
                seqs.append(bus.publish("tick", {"tid": tid, "n": n}))

        threads = [threading.Thread(target=work, args=(tid,))
                   for tid in range(threads_n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        total = threads_n * per
        self.assertEqual(sorted(seqs), list(range(1, total + 1)))
        self.assertTrue(bus.flush(timeout=30))
        self.assertEqual(sorted(received),
                         [(tid, n) for tid in range(threads_n)
                          for n in range(per)])
        self.assertEqual(sorted(r["seq"] for r in self.journal_records()),
                         list(range(1, total + 1)))
        self.assertEqual(bus.stats()["subscribers"]["all"]["dropped"], 0)

    def test_randomized_timing_matches_syncbus(self):
        rng = random.Random(20260921)
        sync = SyncBus()
        bus = self.open_bus(backlog=1024)
        names = ["alpha", "beta", "gamma", "delta"]
        patterns = ["**", "order.**", "order.paid", "user.created"]
        topics = ["order.paid", "order.failed", "user.created", "user.deleted"]
        sync_seen = {name: [] for name in names}
        bus_seen = {name: [] for name in names}
        subscribed = []
        for step in range(300):
            if (subscribed and rng.random() < 0.7) or len(subscribed) == len(names):
                topic = rng.choice(topics)
                payload = {"step": step}
                sync.publish(topic, payload)
                bus.publish(topic, payload)
            else:
                name = rng.choice([n for n in names if n not in subscribed])
                subscribed.append(name)
                pattern = rng.choice(patterns)
                sync.subscribe(name, self.recorder(sync_seen, name), pattern)
                bus.subscribe(name, self.recorder(bus_seen, name), pattern)
        self.assertTrue(bus.flush(timeout=30))
        for name in subscribed:
            self.assertEqual(bus_seen[name], sync_seen[name], name)


class TestBounds(OrderedBusCase):
    def test_window_does_not_grow(self):
        bus = self.open_bus(window=8)
        for n in range(100):
            bus.publish("tick", n)
        stats = bus.stats()
        self.assertEqual(stats["high_water"], 100)
        self.assertEqual(stats["window_size"], 8)
        self.assertEqual(stats["window_low"], 93)

    def test_stats_shape(self):
        bus = self.open_bus()
        bus.subscribe("a", lambda t, p: None)
        bus.publish("tick", 1)
        self.assertTrue(bus.flush(timeout=5))
        stats = bus.stats()
        self.assertEqual(stats["high_water"], 1)
        self.assertEqual(stats["window_low"], 1)
        self.assertEqual(stats["window_size"], 1)
        info = stats["subscribers"]["a"]
        self.assertEqual(info["state"], "live")
        self.assertEqual(info["delivered"], 1)
        self.assertEqual(info["dropped"], 0)
        self.assertEqual(info["pending"], 0)


if __name__ == "__main__":
    unittest.main()
