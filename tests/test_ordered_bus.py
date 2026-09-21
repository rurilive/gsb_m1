"""OrderedBus 的编号、重放、背压与重启口径测试。"""

import json
import os
import random
import tempfile
import threading
import time
import unittest

from eventwire.bus import OrderedBus, SyncBus, WindowExpired


def recorder(log, name):
    def handler(topic, payload):
        log.append((name, topic, payload))
    return handler


class OrderedBusTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "events.jsonl")

    def open_bus(self, **kwargs):
        bus = OrderedBus(self.path, **kwargs)
        self.addCleanup(bus.close)
        return bus

    def journal_records(self):
        with open(self.path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


class TestSequencing(OrderedBusTest):
    def test_publish_assigns_monotonic_seq_and_persists(self):
        bus = self.open_bus()
        self.assertEqual([bus.publish("a.b", {"i": i}) for i in range(3)],
                         [1, 2, 3])
        self.assertEqual([r["seq"] for r in self.journal_records()], [1, 2, 3])

    def test_same_seq_republish_is_dropped(self):
        bus = self.open_bus()
        log = []
        bus.subscribe("audit", recorder(log, "audit"))
        bus.publish("a.b", 1)
        bus.publish("a.b", 2)
        self.assertEqual(bus.publish("a.b", 1, seq=1), 1)
        self.assertTrue(bus.wait_idle())
        self.assertEqual(len(log), 2)
        self.assertEqual(len(self.journal_records()), 2)
        self.assertEqual(bus.stats()["duplicates"], 1)

    def test_seq_gap_is_rejected(self):
        bus = self.open_bus()
        bus.publish("a.b", 1)
        with self.assertRaises(ValueError):
            bus.publish("a.b", 2, seq=5)
        with self.assertRaises(ValueError):
            bus.publish("a.b", 2, seq=0)

    def test_multithreaded_publish_has_no_dup_no_hole(self):
        bus = self.open_bus(window=128, backlog=4096)
        received = {}
        for name in ("s1", "s2", "s3"):
            bus.subscribe(name, recorder(received.setdefault(name, []), name))
        total_per_thread = 250

        def publisher(base):
            for i in range(total_per_thread):
                bus.publish("stress.tick", {"base": base, "i": i})

        threads = [threading.Thread(target=publisher, args=(n,))
                   for n in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(bus.wait_idle(timeout=30))
        expected_events = sorted(
            (base, i) for base in range(4) for i in range(total_per_thread))
        for name, log in received.items():
            got = sorted((payload["base"], payload["i"])
                         for _, _, payload in log)
            self.assertEqual(got, expected_events, name)
        stats = bus.stats()
        self.assertEqual(stats["watermark"], 4 * total_per_thread)
        for name in received:
            self.assertEqual(stats["subscribers"][name]["dropped"], 0)
        journal_seqs = [r["seq"] for r in self.journal_records()]
        self.assertEqual(journal_seqs,
                         list(range(1, 4 * total_per_thread + 1)))


class TestReplay(OrderedBusTest):
    def test_since_replays_window_in_order_then_live(self):
        bus = self.open_bus(window=8)
        for i in range(1, 7):
            bus.publish("order.paid", {"id": i})
        log = []
        bus.subscribe("replay", recorder(log, "replay"), since=3)
        bus.publish("order.paid", {"id": 7})
        self.assertTrue(bus.wait_idle())
        self.assertEqual([payload["id"] for _, _, payload in log],
                         [4, 5, 6, 7])

    def test_since_none_means_live_only(self):
        bus = self.open_bus()
        bus.publish("a.b", 1)
        log = []
        bus.subscribe("live", recorder(log, "live"))
        bus.publish("a.b", 2)
        self.assertTrue(bus.wait_idle())
        self.assertEqual([payload for _, _, payload in log], [2])

    def test_since_older_than_window_raises(self):
        bus = self.open_bus(window=4)
        for i in range(10):
            bus.publish("a.b", i)
        with self.assertRaises(WindowExpired):
            bus.subscribe("old", recorder([], "old"), since=4)
        log = []
        bus.subscribe("edge", recorder(log, "edge"), since=6)
        self.assertTrue(bus.wait_idle())
        self.assertEqual([payload for _, _, payload in log], [6, 7, 8, 9])

    def test_pattern_filters_replay_and_live(self):
        bus = self.open_bus()
        bus.publish("order.paid", 1)
        bus.publish("order.shipped", 2)
        log = []
        bus.subscribe("paid", recorder(log, "paid"), "order.paid", since=0)
        bus.publish("order.paid", 3)
        bus.publish("order.shipped", 4)
        self.assertTrue(bus.wait_idle())
        self.assertEqual([payload for _, _, payload in log], [1, 3])


class TestBackpressure(OrderedBusTest):
    def test_slow_subscriber_does_not_block_others_and_drops_counted(self):
        bus = self.open_bus(backlog=2, overflow="drop")
        entered = threading.Event()
        release = threading.Event()
        slow_log = []

        def slow(topic, payload):
            entered.set()
            release.wait(5)
            slow_log.append(payload)

        bus.subscribe("slow", slow)
        fast_log = []
        bus.subscribe("fast", recorder(fast_log, "fast"))
        bus.publish("a.b", 1)
        self.assertTrue(entered.wait(5))
        started = time.perf_counter()
        for i in range(2, 6):
            bus.publish("a.b", i)
            time.sleep(0.01)  # 给 fast 的工作线程留排空时间，积压只算 slow 的
        self.assertLess(time.perf_counter() - started, 1.0)
        release.set()
        self.assertTrue(bus.wait_idle())
        stats = bus.stats()["subscribers"]
        self.assertEqual(slow_log, [1, 2, 3])
        self.assertEqual(stats["slow"]["dropped"], 2)
        self.assertEqual(stats["slow"]["state"], "live")
        self.assertEqual(
            [payload for _, _, payload in fast_log], [1, 2, 3, 4, 5])
        self.assertEqual(stats["fast"]["dropped"], 0)

    def test_disconnect_overflow_marks_state(self):
        bus = self.open_bus(backlog=1, overflow="disconnect")
        entered = threading.Event()
        release = threading.Event()

        def slow(topic, payload):
            entered.set()
            release.wait(5)

        bus.subscribe("slow", slow)
        bus.publish("a.b", 1)
        self.assertTrue(entered.wait(5))
        bus.publish("a.b", 2)
        bus.publish("a.b", 3)
        release.set()
        self.assertTrue(bus.wait_idle())
        sub = bus.stats()["subscribers"]["slow"]
        self.assertEqual(sub["state"], "disconnected")
        self.assertEqual(sub["delivered"], 1)
        self.assertGreaterEqual(sub["dropped"], 1)
        bus.publish("a.b", 4)
        self.assertEqual(bus.stats()["subscribers"]["slow"]["dropped"],
                         sub["dropped"] + 1)

    def test_window_and_backlog_stay_bounded(self):
        bus = self.open_bus(window=8, backlog=4)
        release = threading.Event()
        entered = threading.Event()

        def slow(topic, payload):
            entered.set()
            release.wait(5)

        bus.subscribe("slow", slow)
        for i in range(1000):
            bus.publish("a.b", i)
        stats = bus.stats()
        self.assertEqual(stats["window"], 8)
        self.assertEqual(stats["window_floor"], 993)
        self.assertLessEqual(stats["subscribers"]["slow"]["pending"], 4)
        release.set()
        self.assertTrue(bus.wait_idle())


class TestRestart(OrderedBusTest):
    def test_reopen_continues_seq_without_resend_or_gap(self):
        bus = self.open_bus()
        for i in range(1, 6):
            bus.publish("a.b", i)
        bus.close()

        bus2 = self.open_bus()
        self.assertEqual(bus2.stats()["watermark"], 5)
        self.assertEqual(bus2.publish("a.b", 6), 6)
        log = []
        bus2.subscribe("replay", recorder(log, "replay"), since=0)
        self.assertTrue(bus2.wait_idle())
        self.assertEqual([payload for _, _, payload in log], [1, 2, 3, 4, 5, 6])
        self.assertEqual([r["seq"] for r in self.journal_records()],
                         [1, 2, 3, 4, 5, 6])

    def test_reopen_respects_window_size(self):
        bus = self.open_bus(window=3)
        for i in range(10):
            bus.publish("a.b", i)
        bus.close()

        bus2 = self.open_bus(window=3)
        stats = bus2.stats()
        self.assertEqual(stats["watermark"], 10)
        self.assertEqual(stats["window_floor"], 8)
        with self.assertRaises(WindowExpired):
            bus2.subscribe("old", recorder([], "old"), since=5)


class TestParityWithSyncBus(OrderedBusTest):
    def test_random_interleaving_matches_sync_bus(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                self._run_parity_round(seed)

    def _run_parity_round(self, seed):
        rng = random.Random(seed)
        topics = ["order.paid", "order.shipped", "gateway.retry", "tick"]
        patterns = ["**", "order.*", "order.paid", "gateway.**"]
        names = ["alpha", "beta", "gamma"]
        sync = SyncBus()
        ordered = self.open_bus(window=1024, backlog=4096)
        sync_log = {name: [] for name in names}
        ordered_log = {name: [] for name in names}
        active = set()

        for _ in range(300):
            op = rng.random()
            name = rng.choice(names)
            if op < 0.25 or not active:
                pattern = rng.choice(patterns)
                sync.subscribe(name, recorder(sync_log[name], name), pattern)
                ordered.subscribe(
                    name, recorder(ordered_log[name], name), pattern)
                active.add(name)
            elif op < 0.35 and len(active) > 1:
                if name in active:
                    sync.unsubscribe(name)
                    ordered.unsubscribe(name)
                    active.discard(name)
            else:
                topic = rng.choice(topics)
                payload = {"n": rng.randrange(1000)}
                sync.publish(topic, payload)
                ordered.publish(topic, payload)
        self.assertTrue(ordered.wait_idle(timeout=30))
        for name in names:
            self.assertEqual(sync_log[name], ordered_log[name], name)


class TestStats(OrderedBusTest):
    def test_stats_reports_watermark_floor_and_per_subscriber(self):
        bus = self.open_bus(window=4)
        for i in range(6):
            bus.publish("a.b", i)
        bus.subscribe("audit", recorder([], "audit"))
        self.assertTrue(bus.wait_idle())
        stats = bus.stats()
        self.assertEqual(stats["watermark"], 6)
        self.assertEqual(stats["window_floor"], 3)
        self.assertEqual(stats["window"], 4)
        self.assertEqual(stats["duplicates"], 0)
        sub = stats["subscribers"]["audit"]
        self.assertEqual(sub["delivered"], 0)
        self.assertEqual(sub["dropped"], 0)
        self.assertEqual(sub["state"], "live")
        self.assertEqual(sub["pending"], 0)


if __name__ == "__main__":
    unittest.main()
