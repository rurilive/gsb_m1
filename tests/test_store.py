"""Store 现有行为的锁定测试：滚段、读写、重启、IO 计账。"""

import unittest

from segpile import MemoryBackend, SimDevice, Store


class TestWriteAndRead(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryBackend()
        self.device = SimDevice()
        self.store = Store(self.backend, self.device, segment_limit=4)

    def test_empty_store_has_no_active_segment(self):
        self.assertIsNone(self.store.active)
        self.assertEqual(self.store.segments(), [])
        self.assertIsNone(self.store.get("a"))

    def test_put_then_get(self):
        self.store.put("a", 1)
        self.assertEqual(self.store.get("a"), 1)
        self.assertIsNone(self.store.get("zzz"))

    def test_overwrite_same_key(self):
        self.store.put("a", 1)
        self.store.put("a", 2)
        self.assertEqual(self.store.get("a"), 2)
        self.assertEqual(len(self.store.segments()), 1)

    def test_none_key_rejected(self):
        with self.assertRaises(ValueError):
            self.store.put(None, 1)

    def test_segment_limit_must_be_positive(self):
        with self.assertRaises(ValueError):
            Store(self.backend, self.device, segment_limit=0)

    def test_rotate_creates_new_segment(self):
        for i in range(4):
            self.store.put("k%d" % i, i)
        self.assertEqual(len(self.store.segments()), 1)
        self.assertEqual(self.store.active.seq, 0)
        self.store.put("k4", 4)
        self.assertEqual(len(self.store.segments()), 2)
        self.assertEqual(self.store.active.seq, 1)
        self.assertEqual(self.store.active.size, 1)

    def test_newer_segment_shadows_older(self):
        for i in range(4):
            self.store.put("k%d" % i, i)
        self.store.put("k4", 4)
        self.store.put("k0", 100)
        self.assertEqual(self.store.get("k0"), 100)
        self.assertEqual(self.store.get("k4"), 4)

    def test_snapshot_agrees_with_get(self):
        for i in range(9):
            self.store.put("k%d" % (i % 5), i)
        snap = self.store.snapshot()
        self.assertEqual(sorted(snap), ["k0", "k1", "k2", "k3", "k4"])
        for key in snap:
            self.assertEqual(self.store.get(key), snap[key])


class TestLatency(unittest.TestCase):
    def setUp(self):
        self.device = SimDevice()
        self.store = Store(MemoryBackend(), self.device, segment_limit=4)

    def test_idle_put_costs_one_io_unit(self):
        self.store.put("a", 1)
        self.device.advance(100)
        self.assertAlmostEqual(self.store.put("b", 1), 1.0)

    def test_rotation_pays_segment_flush_and_metadata(self):
        for i in range(4):
            self.store.put("k%d" % i, i)
        self.device.advance(100)
        self.assertAlmostEqual(self.store.put("k4", 4), 3.0)

    def test_put_latency_includes_queue_wait(self):
        self.store.put("a", 1)
        self.device.advance(100)
        self.device.reserve("read", 5)
        self.assertAlmostEqual(self.store.put("b", 2), 6.0)

    def test_unit_cost_is_configurable_and_read_counted(self):
        device = SimDevice(unit_cost=0.5)
        store = Store(MemoryBackend(), device, segment_limit=4)
        store.put("a", 1)
        device.advance(100)
        self.assertAlmostEqual(store.put("b", 2), 0.5)
        self.assertEqual(store.get("a"), 1)
        self.assertEqual(device.read_units, 1)


class TestDevice(unittest.TestCase):
    def test_charge_blocks_and_moves_the_clock(self):
        device = SimDevice()
        self.assertEqual(device.charge("read", 3), 3.0)
        self.assertEqual(device.now(), 3.0)
        self.assertTrue(device.free())
        self.assertEqual((device.read_units, device.write_units), (3, 0))

    def test_reserve_holds_the_device_without_moving_the_clock(self):
        device = SimDevice()
        self.assertEqual(device.reserve("read", 3), 3.0)
        self.assertEqual(device.now(), 0.0)
        self.assertFalse(device.free())
        self.assertEqual(device.charge("write", 1), 4.0)
        self.assertEqual(device.now(), 4.0)
        with self.assertRaises(ValueError):
            device.reserve("read", -1)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryBackend()
        self.store = Store(self.backend, SimDevice(), segment_limit=4)

    def test_reopen_sees_same_segments_values_and_active(self):
        for i in range(9):
            self.store.put("k%d" % i, i)
        reopened = Store(self.backend, SimDevice(), segment_limit=4)
        self.assertEqual(
            [(s.sid, s.seq, s.size) for s in reopened.segments()],
            [(s.sid, s.seq, s.size) for s in self.store.segments()],
        )
        self.assertEqual(reopened.active.sid, self.store.active.sid)
        for i in range(9):
            self.assertEqual(reopened.get("k%d" % i), i)

    def test_meta_tracks_next_ids_and_active(self):
        for i in range(5):
            self.store.put("k%d" % i, i)
        meta = self.backend.load_meta()
        self.assertEqual(meta["next_sid"], 2)
        self.assertEqual(meta["next_seq"], 2)
        self.assertEqual(meta["active"], self.store.active.sid)
        self.assertEqual(len(meta["segments"]), 2)


if __name__ == "__main__":
    unittest.main()
