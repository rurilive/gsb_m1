"""ModuloRouter 现有行为的锁定测试。"""

import unittest

from shard.router import ModuloRouter, Router


class TestRouterBase(unittest.TestCase):
    def test_nodes_returns_copy(self):
        r = Router(["a", "b"])
        r.nodes.append("c")
        self.assertEqual(r.nodes, ["a", "b"])

    def test_dedup_on_init(self):
        r = Router(["a", "b", "a"])
        self.assertEqual(r.nodes, ["a", "b"])

    def test_add_and_remove(self):
        r = Router(["a"])
        r.add("b")
        r.add("b")  # 重复 add 静默
        self.assertEqual(r.nodes, ["a", "b"])
        r.remove("a")
        r.remove("zz")  # 不存在也静默
        self.assertEqual(r.nodes, ["b"])


class TestModuloRouter(unittest.TestCase):
    def test_route_is_deterministic(self):
        r = ModuloRouter(["n1", "n2", "n3"])
        self.assertEqual(r.route("user:42"), r.route("user:42"))

    def test_route_only_returns_known_nodes(self):
        r = ModuloRouter(["n1", "n2", "n3"])
        for i in range(200):
            self.assertIn(r.route(f"k{i}"), {"n1", "n2", "n3"})

    def test_empty_raises_keyerror(self):
        r = ModuloRouter([])
        with self.assertRaises(KeyError):
            r.route("x")

    def test_single_node_routes_all(self):
        r = ModuloRouter(["only"])
        for i in range(50):
            self.assertEqual(r.route(f"k{i}"), "only")

    def test_remove_current_node(self):
        r = ModuloRouter(["n1", "n2"])
        n1_first = r.route("alpha") == "n1"
        r.remove("n1")
        self.assertEqual(r.route("alpha"), "n2" if n1_first else r.route("alpha"))

    def test_distribution_reasonable(self):
        # 3 节点 3000 个 key，每节点分到的比例在 25%~42% 之间（防写挂）
        r = ModuloRouter(["n1", "n2", "n3"])
        counts = {"n1": 0, "n2": 0, "n3": 0}
        for i in range(3000):
            counts[r.route(f"key-{i}")] += 1
        for c in counts.values():
            self.assertGreater(c, 750)
            self.assertLess(c, 1250)


if __name__ == "__main__":
    unittest.main()
