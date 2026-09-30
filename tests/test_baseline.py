"""NaiveDisjointSets 现有行为的锁定测试（朴素逐元素改名与线性扫描口径）。"""

import unittest

from dsu.core import (
    BadElement,
    BadWeight,
    Erro,
    NaiveDisjointSets,
    NotConnected,
    UnknownNode,
)


def fresh():
    """登记 0 到 5 共六个孤立元素，计数从零起步。"""
    uf = NaiveDisjointSets()
    for x in range(6):
        uf.add(x)
    return uf


class TestAdd(unittest.TestCase):
    def test_elements_sorted(self):
        uf = fresh()
        self.assertEqual(uf.elements(), [0, 1, 2, 3, 4, 5])

    def test_add_is_idempotent(self):
        uf = fresh()
        uf.union(0, 1)
        uf.add(0)
        self.assertEqual(uf.group_members(0), [0, 1])

    def test_contains(self):
        uf = fresh()
        self.assertTrue(uf.contains(3))
        self.assertFalse(uf.contains(9))

    def test_negative_element_rejected(self):
        uf = NaiveDisjointSets()
        with self.assertRaises(BadElement):
            uf.add(-1)

    def test_non_int_element_rejected(self):
        uf = NaiveDisjointSets()
        with self.assertRaises(BadElement):
            uf.add("x")

    def test_bad_element_is_base_error(self):
        uf = NaiveDisjointSets()
        with self.assertRaises(Erro):
            uf.add(None)


class TestQuery(unittest.TestCase):
    def test_singleton_is_own_representative(self):
        uf = fresh()
        self.assertEqual(uf.find(0), 0)

    def test_unknown_node_rejected(self):
        uf = fresh()
        with self.assertRaises(UnknownNode):
            uf.find(99)

    def test_unknown_node_is_base_error(self):
        uf = fresh()
        with self.assertRaises(Erro):
            uf.find(99)

    def test_connected_same_point(self):
        uf = fresh()
        self.assertTrue(uf.connected(2, 2))

    def test_disconnected_pair(self):
        uf = fresh()
        self.assertFalse(uf.connected(0, 1))

    def test_disconnected_shares_no_representative(self):
        uf = fresh()
        self.assertNotEqual(uf.find(0), uf.find(1))

    def test_size_of_singleton(self):
        uf = fresh()
        self.assertEqual(uf.size(4), 1)

    def test_group_members_sorted(self):
        uf = fresh()
        uf.union(3, 5)
        uf.union(3, 4)
        self.assertEqual(uf.group_members(3), [3, 4, 5])


class TestUnion(unittest.TestCase):
    def test_union_returns_true_once(self):
        uf = fresh()
        self.assertTrue(uf.union(0, 1))
        self.assertFalse(uf.union(0, 1))

    def test_union_makes_connected(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(2, 3)
        uf.union(1, 2)
        self.assertTrue(uf.connected(0, 3))

    def test_self_union_is_noop(self):
        uf = fresh()
        self.assertFalse(uf.union(2, 2))
        self.assertEqual(uf.group_members(2), [2])

    def test_size_grows(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(0, 2)
        self.assertEqual(uf.size(0), 3)

    def test_component_count(self):
        uf = fresh()
        self.assertEqual(uf.component_count(), 6)
        uf.union(0, 1)
        self.assertEqual(uf.component_count(), 5)

    def test_component_sizes_sorted(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(0, 2)
        self.assertEqual(uf.component_sizes(), [1, 1, 1, 3])

    def test_groups_ordered_by_min_member(self):
        uf = fresh()
        uf.union(4, 5)
        uf.union(0, 1)
        self.assertEqual(uf.groups(), [[0, 1], [2], [3], [4, 5]])


class TestWeighted(unittest.TestCase):
    def test_weighted_union_and_relate(self):
        uf = fresh()
        uf.union_weighted(1, 0, 5)
        self.assertEqual(uf.relate(1, 0), 5)

    def test_negative_weight(self):
        uf = fresh()
        uf.union_weighted(1, 0, -3)
        self.assertEqual(uf.relate(1, 0), -3)

    def test_zero_weight(self):
        uf = fresh()
        uf.union_weighted(1, 0, 0)
        self.assertEqual(uf.relate(1, 0), 0)

    def test_transitive_offsets(self):
        uf = fresh()
        uf.union_weighted(1, 0, 2)
        uf.union_weighted(2, 1, 3)
        self.assertEqual(uf.relate(2, 0), 5)
        self.assertEqual(uf.relate(2, 1), 3)

    def test_relate_disconnected_raises(self):
        uf = fresh()
        with self.assertRaises(NotConnected):
            uf.relate(0, 1)

    def test_non_int_weight_rejected(self):
        uf = fresh()
        with self.assertRaises(BadWeight):
            uf.union_weighted(0, 1, 1.5)

    def test_bad_weight_is_base_error(self):
        uf = fresh()
        with self.assertRaises(Erro):
            uf.union_weighted(0, 1, True)


class TestDynamicCycle(unittest.TestCase):
    def test_add_edge_merges_new_edge(self):
        uf = fresh()
        self.assertTrue(uf.add_edge(0, 1))
        self.assertEqual(uf.count_merges(), 1)

    def test_add_edge_reports_cycle(self):
        uf = fresh()
        uf.add_edge(0, 1)
        uf.add_edge(1, 2)
        self.assertFalse(uf.add_edge(0, 2))

    def test_add_edge_registers_unknown(self):
        uf = NaiveDisjointSets()
        uf.add_edge(7, 8)
        self.assertEqual(sorted(uf.elements()), [7, 8])

    def test_would_close_cycle_is_pure(self):
        uf = fresh()
        before = uf.component_count()
        self.assertFalse(uf.would_close_cycle(0, 1))
        self.assertEqual(uf.component_count(), before)

    def test_would_close_cycle_after_merge(self):
        uf = fresh()
        uf.union(2, 3)
        self.assertTrue(uf.would_close_cycle(2, 3))


class TestCounters(unittest.TestCase):
    def test_merges_only_on_real_merge(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(1, 0)
        self.assertEqual(uf.count_merges(), 1)

    def test_renames_grow_with_moves(self):
        uf = fresh()
        uf.union(0, 1)
        uf.union(0, 2)
        self.assertEqual(uf.count_renames(), 2)

    def test_find_counts_one_query(self):
        uf = fresh()
        uf.find(0)
        self.assertEqual(uf.count_queries(), 1)

    def test_connected_counts_one_query(self):
        uf = fresh()
        uf.connected(0, 1)
        self.assertEqual(uf.count_queries(), 1)

    def test_relate_counts_one_query_even_on_failure(self):
        uf = fresh()
        with self.assertRaises(NotConnected):
            uf.relate(0, 1)
        self.assertEqual(uf.count_queries(), 1)

    def test_union_does_not_count_queries(self):
        uf = fresh()
        uf.union(0, 1)
        self.assertEqual(uf.count_queries(), 0)

    def test_size_does_not_count_queries(self):
        uf = fresh()
        uf.size(0)
        self.assertEqual(uf.count_queries(), 0)

    def test_scans_grow_with_find(self):
        uf = fresh()
        uf.union(0, 1)
        before = uf.count_scans()
        uf.find(1)
        self.assertGreater(uf.count_scans(), before)

    def test_cost_report_keys(self):
        uf = fresh()
        self.assertEqual(
            sorted(uf.cost_report()),
            ["merges", "queries", "renames", "scans"],
        )


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_sequence(self):
        seq = [(0, 1), (2, 3), (1, 2), (4, 5), (3, 4)]
        first = fresh()
        second = fresh()
        for a, b in seq:
            first.union(a, b)
            second.union(a, b)
        self.assertEqual(first.groups(), second.groups())
        self.assertEqual(first.count_renames(), second.count_renames())
        self.assertEqual(first.count_merges(), second.count_merges())

    def test_groups_stable_on_repeat(self):
        uf = fresh()
        uf.union(0, 1)
        self.assertEqual(uf.groups(), uf.groups())


if __name__ == "__main__":
    unittest.main()
