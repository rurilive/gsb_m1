"""treecover 现有朴素行为的锁定测试（基线，一字不改）。"""

import unittest

from treecover import (
    CoverError,
    EmptyTreeError,
    NotATreeError,
    Tree,
    enumerate_subsets,
    is_dominating_set,
    is_independent_set,
    is_vertex_cover,
    max_independent_set,
    max_weight_independent_set,
    min_dominating_set,
    min_vertex_cover,
    subset_check_count,
    weighted_min_dominating_set,
)


def chain(nodes):
    """按给定顶点顺序连成一条链。"""
    t = Tree(nodes[0])
    for i in range(len(nodes) - 1):
        t.add_edge(nodes[i], nodes[i + 1])
    return t


def star(center, leaves):
    """以 center 为中心的星形树。"""
    t = Tree(center)
    for leaf in leaves:
        t.add_edge(center, leaf)
    return t


def sample_tree():
    """根 1，主链 1-2-3-4，3 号上挂两个叶子 5、6。"""
    t = Tree(1)
    for u, v in [(1, 2), (2, 3), (3, 4), (3, 5), (3, 6)]:
        t.add_edge(u, v)
    return t


class TestTreeConstruction(unittest.TestCase):
    def test_vertices_sorted(self):
        t = Tree(3)
        t.add_edge(3, 1)
        t.add_edge(3, 2)
        self.assertEqual(t.vertices(), [1, 2, 3])

    def test_neighbors_sorted(self):
        t = star(0, [3, 1, 2])
        self.assertEqual(t.neighbors(0), [1, 2, 3])

    def test_edges_normalized(self):
        t = Tree(2)
        t.add_edge(2, 1)
        self.assertEqual(t.edges(), [(1, 2)])

    def test_edge_weight_both_directions(self):
        t = Tree(0)
        t.add_edge(0, 1, 7)
        self.assertEqual(t.edge_weight(0, 1), 7)
        self.assertEqual(t.edge_weight(1, 0), 7)

    def test_self_loop_rejected(self):
        t = Tree(1)
        with self.assertRaises(CoverError):
            t.add_edge(1, 1)

    def test_vertex_weights_default_one(self):
        t = sample_tree()
        self.assertEqual(t.vertex_weights(), {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1})

    def test_vertex_weights_override(self):
        t = chain([1, 2])
        self.assertEqual(t.vertex_weights({2: -3}), {1: 1, 2: -3})


class TestSubsetEnumeration(unittest.TestCase):
    def test_enumerate_three(self):
        got = list(enumerate_subsets([2, 1, 3]))
        want = [(), (1,), (2,), (1, 2), (3,), (1, 3), (2, 3), (1, 2, 3)]
        self.assertEqual(got, want)

    def test_enumerate_single(self):
        self.assertEqual(list(enumerate_subsets([5])), [(), (5,)])

    def test_subset_check_count_is_power_of_two(self):
        t = sample_tree()
        self.assertEqual(subset_check_count(t), 64)


class TestSetPredicates(unittest.TestCase):
    def test_dominating_predicate(self):
        t = chain([1, 2, 3])
        self.assertTrue(is_dominating_set(t, (2,)))
        self.assertFalse(is_dominating_set(t, (1,)))

    def test_cover_predicate(self):
        t = chain([1, 2, 3])
        self.assertTrue(is_vertex_cover(t, (2,)))
        self.assertFalse(is_vertex_cover(t, (1,)))

    def test_independent_predicate(self):
        t = chain([1, 2, 3])
        self.assertTrue(is_independent_set(t, (1, 3)))
        self.assertFalse(is_independent_set(t, (1, 2)))


class TestMinDominatingSet(unittest.TestCase):
    def test_single_node(self):
        t = Tree(9)
        self.assertEqual(min_dominating_set(t), (1, (9,)))

    def test_two_nodes(self):
        t = Tree(1)
        t.add_edge(1, 2)
        self.assertEqual(min_dominating_set(t), (1, (1,)))

    def test_chain_three(self):
        self.assertEqual(min_dominating_set(chain([1, 2, 3])), (1, (2,)))

    def test_chain_four(self):
        # {1,3} 与 {2,3} 都最小，并列取字典序小的 (1,3)
        self.assertEqual(min_dominating_set(chain([1, 2, 3, 4])), (2, (1, 3)))

    def test_star_tie_takes_lexicographically_smallest(self):
        # 星心 0 与叶子 1 单独都能支配全树，并列取字典序小的 (0,)
        self.assertEqual(min_dominating_set(star(0, [1, 2, 3])), (1, (0,)))

    def test_sample_tree(self):
        self.assertEqual(min_dominating_set(sample_tree()), (2, (1, 3)))


class TestMinVertexCover(unittest.TestCase):
    def test_chain_three(self):
        self.assertEqual(min_vertex_cover(chain([1, 2, 3])), (1, (2,)))

    def test_chain_four(self):
        self.assertEqual(min_vertex_cover(chain([1, 2, 3, 4])), (2, (1, 3)))

    def test_star(self):
        self.assertEqual(min_vertex_cover(star(0, [1, 2, 3])), (1, (0,)))

    def test_sample_tree(self):
        self.assertEqual(min_vertex_cover(sample_tree()), (2, (1, 3)))

    def test_two_nodes(self):
        t = Tree(1)
        t.add_edge(1, 2)
        self.assertEqual(min_vertex_cover(t), (1, (1,)))


class TestMaxIndependentSet(unittest.TestCase):
    def test_single_node(self):
        self.assertEqual(max_independent_set(Tree(9)), (1, (9,)))

    def test_chain_four(self):
        self.assertEqual(max_independent_set(chain([1, 2, 3, 4])), (2, (1, 3)))

    def test_star(self):
        self.assertEqual(max_independent_set(star(0, [1, 2, 3])), (3, (1, 2, 3)))

    def test_sample_tree(self):
        self.assertEqual(max_independent_set(sample_tree()), (4, (1, 4, 5, 6)))

    def test_two_nodes(self):
        t = Tree(1)
        t.add_edge(1, 2)
        self.assertEqual(max_independent_set(t), (1, (1,)))


class TestWeighted(unittest.TestCase):
    def test_weighted_dominating_prefers_zero_weight_center(self):
        t = star(0, [1, 2, 3])
        weights = {0: 0, 1: 5, 2: 5, 3: 5}
        self.assertEqual(weighted_min_dominating_set(t, weights), (0, (0,)))

    def test_weighted_dominating_negative(self):
        t = chain([1, 2, 3])
        weights = {1: 2, 2: -4, 3: 2}
        self.assertEqual(weighted_min_dominating_set(t, weights), (-4, (2,)))

    def test_weighted_dominating_default_all_one_matches_unweighted(self):
        t = chain([1, 2, 3, 4])
        cost, chosen = weighted_min_dominating_set(t)
        self.assertEqual(chosen, min_dominating_set(t)[1])
        self.assertEqual(cost, len(chosen))

    def test_max_weight_independent(self):
        t = chain([1, 2, 3])
        weights = {1: 5, 2: 100, 3: 5}
        self.assertEqual(max_weight_independent_set(t, weights), (100, (2,)))

    def test_max_weight_independent_drops_negative_node(self):
        t = chain([1, 2])
        weights = {1: 3, 2: -1}
        self.assertEqual(max_weight_independent_set(t, weights), (3, (1,)))


class TestErrors(unittest.TestCase):
    def test_errors_share_base(self):
        self.assertTrue(issubclass(NotATreeError, CoverError))
        self.assertTrue(issubclass(EmptyTreeError, NotATreeError))

    def test_empty_tree_raises(self):
        with self.assertRaises(EmptyTreeError):
            min_dominating_set(Tree())

    def test_forest_rejected(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        with self.assertRaises(NotATreeError):
            min_vertex_cover(t)

    def test_forest_rejected_for_all_solvers(self):
        t = Tree(1)
        t.add_edge(1, 2)
        t.add_edge(5, 6)
        for solver in (min_dominating_set, min_vertex_cover, max_independent_set):
            with self.assertRaises(NotATreeError):
                solver(t)


class TestDeterminism(unittest.TestCase):
    def test_repeated_dominating_stable(self):
        t = sample_tree()
        self.assertEqual(min_dominating_set(t), min_dominating_set(t))

    def test_repeated_enumerate_stable(self):
        self.assertEqual(list(enumerate_subsets([1, 2, 3])), list(enumerate_subsets([1, 2, 3])))

    def test_solver_does_not_mutate_tree(self):
        t = sample_tree()
        before = t.edges()
        min_dominating_set(t)
        max_independent_set(t)
        self.assertEqual(t.edges(), before)


if __name__ == "__main__":
    unittest.main()
