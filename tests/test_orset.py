"""ORSet 新行为测试：因果合并、墓碑回收、状态编解码。"""

import json
import unittest

from crdtbox.orset import ORSet


def clone(orset):
    """经编解码往返复制一份状态，模拟跨进程传输的副本。"""
    return ORSet.from_dict(json.loads(json.dumps(orset.to_dict())))


def converged_state(orset):
    """去掉副本本地信息（标识与本地视角），只留收敛的 CRDT 状态。"""
    data = orset.to_dict()
    return {k: data[k] for k in ("clock", "adds", "tombstones")}


class TestORSetBasics(unittest.TestCase):
    def test_add_then_contains(self):
        s = ORSet("a")
        s.add("red")
        self.assertTrue(s.contains("red"))
        self.assertFalse(s.contains("blue"))

    def test_add_is_chainable_and_value_sorted(self):
        s = ORSet("a")
        s.add("c").add("a").add("b")
        self.assertEqual(s.value(), ("a", "b", "c"))

    def test_value_is_empty_for_fresh_set(self):
        self.assertEqual(ORSet("a").value(), ())

    def test_discard_removes_element(self):
        s = ORSet("a")
        s.add("red")
        s.discard("red")
        self.assertFalse(s.contains("red"))
        self.assertEqual(s.value(), ())

    def test_discard_absent_element_is_harmless(self):
        s = ORSet("a")
        self.assertIs(s.discard("ghost"), s)
        self.assertEqual(s.value(), ())

    def test_replica_id_must_be_non_empty_string(self):
        with self.assertRaises(ValueError):
            ORSet("")
        with self.assertRaises(ValueError):
            ORSet(None)

    def test_merge_returns_self(self):
        s = ORSet("a")
        self.assertIs(s.merge(ORSet("b")), s)

    def test_merge_rejects_other_types(self):
        with self.assertRaises(TypeError):
            ORSet("a").merge({"red"})


class TestORSetCausalMerge(unittest.TestCase):
    def test_readd_after_discard_works(self):
        s = ORSet("a")
        s.add("red").discard("red").add("red")
        self.assertTrue(s.contains("red"))
        t = ORSet("b")
        t.merge(clone(s))
        self.assertTrue(t.contains("red"))

    def test_concurrent_add_wins_over_discard(self):
        a = ORSet("a")
        a.add("red")
        b = ORSet("b")
        b.merge(clone(a))       # b 先看到 red
        a.discard("red")        # a 删除自己见过的加入
        b.add("red")            # b 并发重新加入，没看到 a 的删除
        a.merge(clone(b))
        b.merge(clone(a))
        self.assertTrue(a.contains("red"))
        self.assertTrue(b.contains("red"))

    def test_observed_removal_still_wins(self):
        a = ORSet("a")
        a.add("red")
        b = ORSet("b")
        b.merge(clone(a))
        b.discard("red")        # b 观测到 red 的加入后再删除
        a.merge(clone(b))
        self.assertFalse(a.contains("red"))
        self.assertEqual(a.value(), ())

    def _three_replica_states(self):
        a = ORSet("a")
        a.add("x").add("y")
        b = ORSet("b")
        b.merge(clone(a))
        b.discard("x").add("z")
        c = ORSet("c")
        c.merge(clone(a))
        c.add("x").add("w")     # 与 b 的删除并发的重入
        return a, b, c

    def test_merge_is_commutative(self):
        a, b, c = self._three_replica_states()
        left = clone(a)
        left.merge(clone(b))
        right = clone(b)
        right.merge(clone(a))
        self.assertEqual(converged_state(left), converged_state(right))

    def test_merge_is_associative(self):
        a, b, c = self._three_replica_states()
        left = clone(a)
        left.merge(clone(b))
        left.merge(clone(c))
        right = clone(a)
        bc = clone(b)
        bc.merge(clone(c))
        right.merge(bc)
        self.assertEqual(converged_state(left), converged_state(right))

    def test_merge_is_idempotent(self):
        a, b, _ = self._three_replica_states()
        a.merge(clone(b))
        snapshot = a.to_dict()
        a.merge(clone(b))
        self.assertEqual(a.to_dict(), snapshot)

    def test_merge_order_does_not_matter(self):
        a, b, c = self._three_replica_states()
        orders = [
            (clone(a), [b, c]),
            (clone(b), [c, a]),
            (clone(c), [a, b]),
        ]
        results = []
        for head, tail in orders:
            for other in tail:
                head.merge(clone(other))
            results.append(head)
        self.assertEqual(converged_state(results[0]), converged_state(results[1]))
        self.assertEqual(converged_state(results[1]), converged_state(results[2]))
        self.assertEqual(results[0].value(), ("w", "x", "y", "z"))

    def test_repeated_add_discard_cycles_converge(self):
        a = ORSet("a")
        for _ in range(3):
            a.add("k").discard("k")
        a.add("k")
        b = clone(a)
        a.merge(clone(b))
        b.merge(clone(a))
        self.assertTrue(a.contains("k"))
        self.assertEqual(converged_state(a), converged_state(b))


class TestORSetTombstoneGC(unittest.TestCase):
    def _removed_state(self):
        a = ORSet("a")
        a.add("red")
        b = ORSet("b")
        b.merge(clone(a))
        a.merge(clone(b))       # a 认识 b，b 还没见过删除
        in_flight = clone(b)    # 删除前发出的旧状态，还在路上
        a.discard("red")
        return a, b, in_flight

    def test_gc_waits_until_all_replicas_saw_removal(self):
        a, b, _ = self._removed_state()
        self.assertEqual(a.gc(), 0)     # b 还没见到删除，墓碑保留
        b.merge(clone(a))
        a.merge(clone(b))               # a 确认 b 已见到删除
        self.assertEqual(a.gc(), 1)
        self.assertEqual(a.gc(), 0)     # 已回收，再次回收无事发生

    def test_gc_does_not_resurrect_removed_element(self):
        a, b, _ = self._removed_state()
        b.merge(clone(a))
        a.merge(clone(b))
        a.gc()
        self.assertFalse(a.contains("red"))
        a.merge(clone(b))               # 与见过删除的副本再合并
        self.assertFalse(a.contains("red"))
        self.assertEqual(a.value(), ())

    def test_in_flight_old_state_cannot_bring_element_back(self):
        a, b, in_flight = self._removed_state()
        a.merge(clone(in_flight))       # 回收前：墓碑挡住旧状态
        self.assertFalse(a.contains("red"))
        b.merge(clone(a))
        a.merge(clone(b))
        a.gc()
        a.merge(clone(in_flight))       # 回收后：时钟挡住旧状态
        self.assertFalse(a.contains("red"))
        self.assertEqual(a.value(), ())

    def test_gc_keeps_unrelated_tombstones(self):
        a, b, _ = self._removed_state()
        a.add("blue")
        b.merge(clone(a))               # b 见到 red 的删除，但还没见过 blue
        a.merge(clone(b))
        a.discard("blue")               # b 没见过这次删除
        self.assertEqual(a.gc(), 1)     # red 的墓碑可回收，blue 的必须留下
        remaining = a.to_dict()["tombstones"]
        self.assertEqual([entry["item"] for entry in remaining], ["blue"])


class TestORSetCodec(unittest.TestCase):
    def _rich_state(self):
        a = ORSet("a")
        a.add("x").add("y")
        b = ORSet("b")
        b.merge(clone(a))
        b.discard("x").add("z")
        a.merge(clone(b))
        a.add("x")                      # 删除后重入
        return a

    def test_round_trip_preserves_everything(self):
        s = self._rich_state()
        restored = ORSet.from_dict(s.to_dict())
        self.assertEqual(restored.to_dict(), s.to_dict())
        self.assertEqual(restored.value(), s.value())
        self.assertEqual(restored.replica_id, s.replica_id)

    def test_round_trip_through_json(self):
        s = self._rich_state()
        payload = json.dumps(s.to_dict())
        restored = ORSet.from_dict(json.loads(payload))
        self.assertEqual(restored.to_dict(), s.to_dict())

    def test_decoded_state_merges_like_the_original(self):
        s = self._rich_state()
        restored = clone(s)
        other = ORSet("c")
        other.add("x").add("w")
        s.merge(clone(other))
        restored.merge(clone(other))
        self.assertEqual(restored.to_dict(), s.to_dict())

    def test_from_dict_rejects_foreign_data(self):
        with self.assertRaises(ValueError):
            ORSet.from_dict({"type": "GCounter"})
        with self.assertRaises(ValueError):
            ORSet.from_dict("not a dict")


if __name__ == "__main__":
    unittest.main()
