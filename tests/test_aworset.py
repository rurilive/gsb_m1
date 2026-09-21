"""AWORSet 新行为测试：合并律、并发加入胜出、墓碑回收、编解码。"""

import json
import unittest

from crdtbox.aworset import AWORSet


def synced_pair():
    """返回一对已同步过初始状态的副本。"""
    a = AWORSet("a")
    b = AWORSet("b")
    a.add("red").add("blue")
    b.merge(a)
    a.merge(b)
    return a, b


def causal_state(s):
    """合并需要收敛的因果状态（replica_id/counter 是本地标识）。"""
    d = s.to_dict()
    return {k: d[k] for k in ("clock", "live", "tombstones")}


class TestAddWinsSemantics(unittest.TestCase):
    def test_readd_after_discard(self):
        s = AWORSet("a")
        s.add("red")
        s.discard("red")
        self.assertFalse(s.contains("red"))
        s.add("red")
        self.assertTrue(s.contains("red"))
        self.assertEqual(s.value(), ("red",))

    def test_concurrent_add_beats_discard(self):
        a, b = synced_pair()
        b.discard("red")   # b 删掉 red
        a.add("red")       # a 并发加回 red，b 的删除看不到这次加入
        a.merge(b)
        b.merge(a)
        self.assertTrue(a.contains("red"))
        self.assertEqual(a.value(), b.value())

    def test_discard_covers_only_seen_adds(self):
        # b 的删除只作用于它见过的加入；a 事后的加入不受影响
        a, b = synced_pair()
        b.discard("red")
        a.add("red")
        a.merge(b)
        self.assertEqual(a.value(), ("blue", "red"))

    def test_stale_state_does_not_resurrect(self):
        a, b = synced_pair()
        stale = AWORSet.loads(b.dumps())  # 删除前的旧快照
        b.discard("red")
        a.merge(b)
        a.merge(stale)  # 还在路上的旧状态带不回已删元素
        self.assertFalse(a.contains("red"))

    def test_merge_rejects_other_types(self):
        with self.assertRaises(TypeError):
            AWORSet("a").merge({"red"})

    def test_replica_id_must_be_non_empty_string(self):
        with self.assertRaises(ValueError):
            AWORSet("")
        with self.assertRaises(ValueError):
            AWORSet(None)


class TestMergeLaws(unittest.TestCase):
    def _three_replicas(self):
        a, b = synced_pair()
        c = AWORSet("c")
        b.discard("red")
        a.add("green")
        c.add("blue")
        c.discard("blue")
        c.add("yellow")
        return a, b, c

    def test_merge_is_commutative(self):
        a, b, _ = self._three_replicas()
        ab = AWORSet.loads(a.dumps()).merge(AWORSet.loads(b.dumps()))
        ba = AWORSet.loads(b.dumps()).merge(AWORSet.loads(a.dumps()))
        self.assertEqual(causal_state(ab), causal_state(ba))

    def test_merge_is_associative(self):
        a, b, c = self._three_replicas()
        left = AWORSet.loads(a.dumps()).merge(AWORSet.loads(b.dumps()))
        left.merge(AWORSet.loads(c.dumps()))
        right = AWORSet.loads(b.dumps()).merge(AWORSet.loads(c.dumps()))
        right = AWORSet.loads(a.dumps()).merge(right)
        self.assertEqual(causal_state(left), causal_state(right))

    def test_merge_is_idempotent(self):
        a, b, c = self._three_replicas()
        a.merge(b).merge(c)
        snapshot = causal_state(a)
        a.merge(b).merge(c)
        a.merge(AWORSet.loads(a.dumps()))
        self.assertEqual(causal_state(a), snapshot)

    def test_converges_regardless_of_order(self):
        a, b, c = self._three_replicas()
        for first, second, third in ((a, b, c), (c, a, b), (b, c, a)):
            merged = AWORSet.loads(first.dumps())
            merged.merge(AWORSet.loads(second.dumps()))
            merged.merge(AWORSet.loads(third.dumps()))
            self.assertEqual(merged.value(), ("blue", "green", "yellow"))


class TestTombstones(unittest.TestCase):
    def _gapped_payload(self):
        # 模拟路上收到的增量状态：只见过 (r,3)，没见过 (r,1)、(r,2)
        return {
            "type": "AWORSet",
            "replica_id": "r",
            "counter": 0,
            "clock": {},
            "live": [["z", [["r", 3]]]],
            "tombstones": [],
        }

    def test_full_state_sync_leaves_no_tombstone(self):
        a, b = synced_pair()
        b.discard("red")  # 删除的点已被时钟覆盖，直接吸收
        self.assertEqual(b.tombstone_count(), 0)

    def test_gap_creates_tombstone_then_clock_reclaims(self):
        s = AWORSet("a")
        s.merge(AWORSet.from_dict(self._gapped_payload()))
        s.discard("z")  # (r,3) 时钟覆盖不到，留下墓碑
        self.assertEqual(s.tombstone_count(), 1)
        # 缺口补齐前，旧状态反复到达也复活不了 z
        s.merge(AWORSet.from_dict(self._gapped_payload()))
        self.assertFalse(s.contains("z"))
        self.assertEqual(s.tombstone_count(), 1)
        # 时钟追上 (r,3)，墓碑回收
        s.merge(AWORSet.from_dict({
            "type": "AWORSet", "replica_id": "r", "counter": 3,
            "clock": {"r": 3}, "live": [], "tombstones": [],
        }))
        self.assertEqual(s.tombstone_count(), 0)
        self.assertFalse(s.contains("z"))

    def test_gc_does_not_resurrect_after_reclaim(self):
        s = AWORSet("a")
        s.merge(AWORSet.from_dict(self._gapped_payload()))
        s.discard("z")
        s.merge(AWORSet.from_dict({
            "type": "AWORSet", "replica_id": "r", "counter": 3,
            "clock": {"r": 3}, "live": [], "tombstones": [],
        }))
        self.assertEqual(s.gc(), 0)  # merge 已顺带回收
        # 回收后旧状态再到达，时钟本身就是屏障
        s.merge(AWORSet.from_dict(self._gapped_payload()))
        self.assertFalse(s.contains("z"))
        self.assertEqual(s.tombstone_count(), 0)


class TestCodec(unittest.TestCase):
    def test_dict_round_trip_preserves_everything(self):
        a, b = synced_pair()
        b.discard("red")
        a.add("green")
        a.merge(b)
        clone = AWORSet.from_dict(a.to_dict())
        self.assertEqual(clone.to_dict(), a.to_dict())
        self.assertEqual(clone.value(), a.value())
        self.assertEqual(clone.replica_id, a.replica_id)

    def test_json_round_trip(self):
        a, _ = synced_pair()
        a.add("标签")
        text = a.dumps()
        json.loads(text)  # 合法 JSON
        self.assertEqual(AWORSet.loads(text).to_dict(), a.to_dict())

    def test_round_trip_preserves_tombstones(self):
        s = AWORSet("a")
        s.merge(AWORSet.from_dict({
            "type": "AWORSet", "replica_id": "r", "counter": 0,
            "clock": {}, "live": [["z", [["r", 3]]]], "tombstones": [],
        }))
        s.discard("z")
        self.assertEqual(s.tombstone_count(), 1)
        clone = AWORSet.loads(s.dumps())
        self.assertEqual(clone.tombstone_count(), 1)

    def test_decoded_state_merges_identically(self):
        a, b = synced_pair()
        b.discard("red")
        direct = AWORSet.loads(a.dumps()).merge(b)
        via_wire = AWORSet.loads(a.dumps()).merge(AWORSet.loads(b.dumps()))
        self.assertEqual(direct.to_dict(), via_wire.to_dict())

    def test_from_dict_rejects_garbage(self):
        with self.assertRaises(ValueError):
            AWORSet.from_dict({"type": "TwoPhaseSet"})
        with self.assertRaises(ValueError):
            AWORSet.from_dict("not a dict")


if __name__ == "__main__":
    unittest.main()
