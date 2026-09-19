"""ConsistentHashRouter 行为测试。"""

import unittest

from shard.router import ConsistentHashRouter, Router

KEYS = [f"key-{i}" for i in range(3000)]


def moved_keys(old, new, keys=KEYS):
    return [k for k in keys if old.route(k) != new.route(k)]


class TestInterface(unittest.TestCase):
    def test_is_router_subclass(self):
        self.assertTrue(issubclass(ConsistentHashRouter, Router))

    def test_route_is_deterministic(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        self.assertEqual(r.route("user:42"), r.route("user:42"))

    def test_route_only_returns_known_nodes(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        for i in range(200):
            self.assertIn(r.route(f"k{i}"), {"n1", "n2", "n3"})


class TestEmptyAndSingle(unittest.TestCase):
    def test_empty_raises_keyerror(self):
        r = ConsistentHashRouter([])
        with self.assertRaises(KeyError):
            r.route("x")

    def test_empty_after_remove_all(self):
        r = ConsistentHashRouter(["only"])
        r.remove("only")
        with self.assertRaises(KeyError):
            r.route("x")

    def test_single_node_routes_all(self):
        r = ConsistentHashRouter(["only"])
        for k in KEYS[:200]:
            self.assertEqual(r.route(k), "only")


class TestMigrationMinimality(unittest.TestCase):
    def test_add_node_moves_only_to_new_node(self):
        old = ConsistentHashRouter(["n1", "n2", "n3"])
        new = ConsistentHashRouter(["n1", "n2", "n3", "n4"])
        moved = moved_keys(old, new)
        # 换归属的 key 必须全部迁往新节点
        for k in moved:
            self.assertEqual(new.route(k), "n4")
        # 理想迁移量约 1/4，允许统计波动但远小于取模路由的近全量
        self.assertLess(len(moved), len(KEYS) * 0.45)
        self.assertGreater(len(moved), 0)

    def test_remove_node_moves_only_its_keys(self):
        old = ConsistentHashRouter(["n1", "n2", "n3"])
        new = ConsistentHashRouter(["n1", "n2"])
        moved = moved_keys(old, new)
        # 只有原本属于 n3 的 key 需要迁移
        self.assertEqual(
            set(moved), {k for k in KEYS if old.route(k) == "n3"}
        )

    def test_add_then_remove_restores_mapping(self):
        old = ConsistentHashRouter(["n1", "n2", "n3"])
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        r.add("n4")
        r.remove("n4")
        for k in KEYS[:500]:
            self.assertEqual(r.route(k), old.route(k))


class TestWeight(unittest.TestCase):
    def test_weight_doubles_share(self):
        r = ConsistentHashRouter(["n1", "n2", "n3"])
        r.set_weight("n1", 2)
        counts = {"n1": 0, "n2": 0, "n3": 0}
        for k in KEYS:
            counts[r.route(k)] += 1
        # n1 权重 2，应接近 n2/n3 的两倍（宽松区间防抖动）
        self.assertGreater(counts["n1"], counts["n2"] * 1.4)
        self.assertGreater(counts["n1"], counts["n3"] * 1.4)

    def test_weight_adjustable_at_runtime(self):
        r = ConsistentHashRouter(["n1", "n2"])
        before = sum(1 for k in KEYS if r.route(k) == "n1")
        r.set_weight("n1", 3)
        after = sum(1 for k in KEYS if r.route(k) == "n1")
        self.assertGreater(after, before)

    def test_invalid_weight_rejected(self):
        r = ConsistentHashRouter(["n1"])
        for bad in (0, -1, 1.5, "2"):
            with self.assertRaises(ValueError):
                r.set_weight("n1", bad)


if __name__ == "__main__":
    unittest.main()
