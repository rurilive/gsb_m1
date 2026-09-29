"""ModuloSharding 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：取模下标、增删节点、lookup 的确定性、空列表
返回，以及取模分片在增删节点时大面积重映射的固有毛病。新增的哈希环行为
（虚拟节点、权重、最小重映射、多副本、均衡度）另建测试文件，不改动本文件。
"""

import unittest

from hashring.modulo import ModuloSharding


KEYS = [f"key-{i}" for i in range(2000)]


class TestModuloLookup(unittest.TestCase):
    def test_empty_returns_none(self):
        s = ModuloSharding()
        self.assertIsNone(s.lookup("any"))

    def test_single_node_owns_every_key(self):
        s = ModuloSharding(["node-a"])
        for k in KEYS[:50]:
            self.assertEqual(s.lookup(k), "node-a")

    def test_lookup_returns_registered_node(self):
        s = ModuloSharding(["node-a", "node-b", "node-c"])
        for k in KEYS:
            self.assertIn(s.lookup(k), {"node-a", "node-b", "node-c"})

    def test_lookup_is_deterministic(self):
        s = ModuloSharding(["node-a", "node-b", "node-c"])
        first = [s.lookup(k) for k in KEYS]
        second = [s.lookup(k) for k in KEYS]
        self.assertEqual(first, second)

    def test_all_nodes_receive_some_keys(self):
        s = ModuloSharding(["node-a", "node-b", "node-c"])
        used = {s.lookup(k) for k in KEYS}
        self.assertEqual(used, {"node-a", "node-b", "node-c"})


class TestModuloGuards(unittest.TestCase):
    def test_duplicate_add_is_noop(self):
        s = ModuloSharding()
        s.add_node("node-a")
        s.add_node("node-a")
        self.assertEqual(s.nodes(), ["node-a"])

    def test_duplicate_add_keeps_lookup_stable(self):
        s = ModuloSharding(["node-a", "node-b"])
        before = [s.lookup(k) for k in KEYS]
        s.add_node("node-a")
        after = [s.lookup(k) for k in KEYS]
        self.assertEqual(before, after)

    def test_empty_node_rejected(self):
        s = ModuloSharding()
        with self.assertRaises(ValueError):
            s.add_node("")
        with self.assertRaises(ValueError):
            s.add_node(None)

    def test_nodes_sorted_and_unique(self):
        s = ModuloSharding(["node-c", "node-a", "node-b"])
        self.assertEqual(s.nodes(), ["node-a", "node-b", "node-c"])

    def test_remove_missing_node_raises(self):
        s = ModuloSharding(["node-a"])
        with self.assertRaises(KeyError):
            s.remove_node("node-b")


class TestModuloRemap(unittest.TestCase):
    def test_remove_node_clears_it_from_ring(self):
        s = ModuloSharding(["node-a", "node-b", "node-c"])
        s.remove_node("node-b")
        used = {s.lookup(k) for k in KEYS}
        self.assertEqual(used, {"node-a", "node-c"})

    def test_add_node_remaps_a_large_fraction(self):
        """取模分片的分母一变全盘重排，这是现有实现的固有毛病。"""
        s = ModuloSharding(["node-a", "node-b", "node-c"])
        before = [s.lookup(k) for k in KEYS]
        s.add_node("node-d")
        after = [s.lookup(k) for k in KEYS]
        changed = sum(1 for a, b in zip(before, after) if a != b)
        # 加第四个节点后下标整体重排，过半 key 都会改归属。
        self.assertGreater(changed, len(KEYS) // 2)


if __name__ == "__main__":
    unittest.main()
