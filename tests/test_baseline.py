"""基线测试：锁住朴素逐点走实现的现状行为，实现升级后一字不许改且必须全绿。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from treemo import (  # noqa: E402
    PathQuerier,
    QueryError,
    InvalidNodeError,
    build_tree,
    node_path,
    step_count,
)

#          0
#        / | \
#       1  2  3
#      / \    | \
#     4   5   6  7
PARENTS = [-1, 0, 0, 0, 1, 1, 3, 3]
WEIGHTS = [3, 1, 4, 5, 2, 7, -1, 6]


class TreeTest(unittest.TestCase):
    def test_build_shape(self):
        t = build_tree(8, PARENTS, WEIGHTS)
        self.assertEqual(t["n"], 8)
        self.assertEqual(t["parent"], PARENTS)
        self.assertEqual(t["children"][0], [1, 2, 3])
        self.assertEqual(t["children"][3], [6, 7])
        self.assertEqual(t["weight"], WEIGHTS)

    def test_build_rejects_bad_shape(self):
        with self.assertRaises(InvalidNodeError):
            build_tree(0, [], [])
        with self.assertRaises(InvalidNodeError):
            build_tree(3, [-1, 0], [1, 2, 3])

    def test_node_path(self):
        t = build_tree(8, PARENTS, WEIGHTS)
        self.assertEqual(node_path(t, 4, 5), [4, 1, 5])
        self.assertEqual(node_path(t, 4, 7), [4, 1, 0, 3, 7])
        self.assertEqual(node_path(t, 2, 2), [2])
        self.assertEqual(node_path(t, 0, 7), [0, 3, 7])


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.q = PathQuerier(8, PARENTS, WEIGHTS)

    def test_path_distinct(self):
        self.assertEqual(self.q.path_distinct(4, 5), 3)  # 2,1,7
        self.assertEqual(self.q.path_distinct(4, 7), 5)  # 2,1,3,5,6
        self.assertEqual(self.q.path_distinct(2, 2), 1)
        self.assertEqual(self.q.path_distinct(0, 7), 3)  # 3,5,6

    def test_path_sum(self):
        self.assertEqual(self.q.path_sum(4, 5), 2 + 1 + 7)
        self.assertEqual(self.q.path_sum(4, 7), 2 + 1 + 3 + 5 + 6)
        self.assertEqual(self.q.path_sum(2, 2), 4)
        self.assertEqual(self.q.path_sum(6, 5), -1 + 5 + 3 + 1 + 7)

    def test_path_max_and_negative(self):
        self.assertEqual(self.q.path_max(4, 5), 7)
        self.assertEqual(self.q.path_max(6, 5), 7)
        self.assertEqual(self.q.path_max(6, 6), -1)
        self.assertEqual(self.q.path_max(0, 0), 3)

    def test_path_count(self):
        self.assertEqual(self.q.path_count(4, 7, 5), 1)
        self.assertEqual(self.q.path_count(0, 7, 3), 1)
        self.assertEqual(self.q.path_count(4, 5, 5), 0)
        self.assertEqual(self.q.path_count(2, 2, 4), 1)

    def test_path_mode_tie_breaks_smallest(self):
        self.assertEqual(self.q.path_mode(3, 1), 1)  # 5,3,1 各一次，取最小
        self.assertEqual(self.q.path_mode(4, 7), 1)  # 2,1,3,5,6 各一次
        self.assertEqual(self.q.path_mode(6, 6), -1)

    def test_run_checksum_and_length(self):
        queries = [(4, 7, 5), (2, 2, 4), (0, 7, -1), (6, 5, 3)]
        results, checksum = self.q.run(queries)
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]["distinct"], 5)
        self.assertEqual(results[0]["sum"], 17)
        self.assertEqual(results[1]["count"], 1)
        self.assertEqual(checksum, 109)

    def test_empty_query_set(self):
        results, checksum = self.q.run([])
        self.assertEqual(results, [])
        self.assertEqual(checksum, 0)

    def test_walk_steps(self):
        self.assertEqual(self.q.walk_steps(4, 5), 2)
        self.assertEqual(self.q.walk_steps(4, 7), 4)
        self.assertEqual(self.q.walk_steps(2, 2), 0)

    def test_invalid_endpoint(self):
        with self.assertRaises(InvalidNodeError):
            self.q.path_sum(0, 8)
        with self.assertRaises(QueryError):
            self.q.path_distinct(-1, 3)


class ScaleAndDeterminismTest(unittest.TestCase):
    def test_step_count_grows_with_depth(self):
        q = PathQuerier(8, PARENTS, WEIGHTS)
        near = step_count(q, 4, 5)
        far = step_count(q, 4, 7)
        self.assertLess(near, far)
        self.assertEqual(far, 5)
        self.assertEqual(step_count(q, 2, 2), 1)

    def test_repeatable(self):
        first = PathQuerier(8, PARENTS, WEIGHTS).run([(4, 7, 5), (6, 5, 3)])
        second = PathQuerier(8, PARENTS, WEIGHTS).run([(4, 7, 5), (6, 5, 3)])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
