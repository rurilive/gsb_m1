"""ConsistentHashRouter 的行为测试。"""

import unittest
from collections import Counter

from shard.router import ConsistentHashRouter, Router

KEYS = [f"object:{i:05d}" for i in range(8000)]


class TestEmptyAndSingle(unittest.TestCase):
    def test_empty_ring_raises_keyerror(self):
        r = ConsistentHashRouter([])
        with self.assertRaises(KeyError):
            r.route("anything")

    def test_route_after_remove_all_raises(self):
        r = ConsistentHashRouter(["a", "b"])
        r.remove("a")
        r.remove("b")
        with self.assertRaises(KeyError):
            r.route("x")

    def test_single_node_routes_all(self):
        r = ConsistentHashRouter(["only"])
        for k in KEYS[:2000]:
            self.assertEqual(r.route(k), "only")

    def test_deterministic(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        for k in KEYS[:500]:
            self.assertEqual(r.route(k), r.route(k))

    def test_only_returns_known_nodes(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        for k in KEYS:
            self.assertIn(r.route(k), {"n1", "n2", "n3"})

    def test_is_a_router(self):
        r = ConsistentHashRouter(["a"])
        self.assertIsInstance(r, Router)
        self.assertEqual(r.nodes, ["a"])


class TestWeights(unittest.TestCase):
    def test_default_virtual_nodes_is_150(self):
        r = ConsistentHashRouter(["a"])
        self.assertEqual(len(r._ring_hashes), 150)

    def test_weight_doubles_virtual_nodes_and_share(self):
        r = ConsistentHashRouter(["cache-a", "cache-b"],
                                 weights={"cache-a": 1, "cache-b": 2})
        counts = Counter(r.route(k) for k in KEYS)
        # 虚拟节点数 1:2
        self.assertEqual(len(r._ring_hashes), 150 * 3)
        self.assertEqual(r.weights, {"cache-a": 1, "cache-b": 2})
        # cache-b 拿到的 key 数大致是 cache-a 的两倍（允许统计波动）
        self.assertGreater(counts["cache-b"], counts["cache-a"] * 1.7)
        self.assertLess(counts["cache-b"], counts["cache-a"] * 2.3)

    def test_set_weight_at_runtime_scales_share(self):
        r = ConsistentHashRouter(["cache-a", "cache-b"])
        r.set_weight("cache-a", 3)
        self.assertEqual(r.weights["cache-a"], 3)
        self.assertEqual(len(r._ring_hashes), 150 * 4)
        counts = Counter(r.route(k) for k in KEYS)
        self.assertGreater(counts["cache-a"], counts["cache-b"] * 2.3)
        self.assertLess(counts["cache-a"], counts["cache-b"] * 3.5)

    def test_lower_weight_at_runtime(self):
        r = ConsistentHashRouter(["cache-a", "cache-b"],
                                 weights={"cache-a": 4, "cache-b": 1})
        r.set_weight("cache-a", 1)
        self.assertEqual(len(r._ring_hashes), 150 * 2)
        counts = Counter(r.route(k) for k in KEYS)
        self.assertGreater(counts["cache-a"], len(KEYS) * 0.35)
        self.assertLess(counts["cache-a"], len(KEYS) * 0.65)

    def test_weight_must_be_positive_integer(self):
        r = ConsistentHashRouter(["cache-a"])
        for bad in (0, -1, 1.5, "2"):
            with self.assertRaises(ValueError):
                r.set_weight("a", bad)

    def test_add_with_weight(self):
        r = ConsistentHashRouter(["a"])
        r.add("b", weight=2)
        self.assertEqual(r.weights, {"a": 1, "b": 2})

    def test_weights_dedupe_nodes(self):
        r = ConsistentHashRouter(["a", "a", "b"], weights={"a": 2})
        self.assertEqual(r.nodes, ["a", "b"])
        self.assertEqual(r.weights, {"a": 2, "b": 1})


class TestMinimalMigration(unittest.TestCase):
    def _moved(self, old, new):
        return sum(1 for k in KEYS if old.route(k) != new.route(k))

    def test_add_node_moves_roughly_share_only(self):
        old = ConsistentHashRouter(["n1", "n2", "n3"])
        new = ConsistentHashRouter(["n1", "n2", "n3", "n4"])
        moved = self._moved(old, new)
        # 理想值是 1/4；留出余量，必须远小于取模路由的 ~3/4
        self.assertLess(moved, len(KEYS) * 0.35)
        self.assertGreater(moved, len(KEYS) * 0.15)
        # 换走的 key 全部去了新节点；老节点之间不互相抢 key
        for k in KEYS:
            if old.route(k) != new.route(k):
                self.assertEqual(new.route(k), "n4")

    def test_unchanged_keys_stay_with_same_node(self):
        old = ConsistentHashRouter(["n1", "n2", "n3"])
        new = ConsistentHashRouter(["n1", "n2", "n3", "n4"])
        for k in KEYS:
            if new.route(k) != "n4":
                self.assertEqual(old.route(k), new.route(k))

    def test_remove_node_redistributes_only_its_keys(self):
        old = ConsistentHashRouter(["n1", "n2", "n3"])
        new = ConsistentHashRouter(["n1", "n3"])
        for k in KEYS:
            before = old.route(k)
            after = new.route(k)
            if before == "n2":
                self.assertIn(after, {"n1", "n3"})
            else:
                self.assertEqual(before, after)

    def test_weight_increase_moves_keys_to_weighted_node(self):
        old = ConsistentHashRouter(["n1", "n2"])
        new = ConsistentHashRouter(["n1", "n2"])
        new.set_weight("n2", 2)
        for k in KEYS:
            after = new.route(k)
            if old.route(k) != after:
                self.assertEqual(after, "n2")

    def test_weight_decrease_only_gives_away_keys(self):
        old = ConsistentHashRouter(["n1", "n2"], weights={"n1": 3, "n2": 1})
        new = ConsistentHashRouter(["n1", "n2"], weights={"n1": 3, "n2": 1})
        new.set_weight("n1", 1)
        for k in KEYS:
            if old.route(k) != new.route(k):
                self.assertEqual(new.route(k), "n2")

    def test_dynamic_add_node_matches_fresh_router(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        r.add("n4")
        fresh = ConsistentHashRouter(["n1", "n2", "n3", "n4"])
        for k in KEYS:
            self.assertEqual(r.route(k), fresh.route(k))

    def test_dynamic_remove_matches_fresh_router(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        r.remove("n2")
        fresh = ConsistentHashRouter(["n1", "n3"])
        for k in KEYS:
            self.assertEqual(r.route(k), fresh.route(k))


if __name__ == "__main__":
    unittest.main()
