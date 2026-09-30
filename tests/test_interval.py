"""基线测试：锁住改造前 intervalx.interval.IntervalSet 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - merge 反复在两两之间比较可连通的区间并成一段；
  - intersection 逐对区间求交后合并去重；
  - coverage_length 与 max_overlap 逐点逐区间判定；
  - contains_pair 用四次端点比较求包含关系；
  - cover_with 逐段搜最少区间数并取下标序列字典序最小者；
  - independent_brute_merge 与 independent_brute_max_overlap 是两条独立慢速做法。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intervalx.interval import (  # noqa: E402
    IntervalSet,
    Erro,
    IntervalErro,
    TargetErro,
    IndexErro,
)


SAMPLE = [(1, 4), (2, 6), (8, 10), (9, 12), (20, 21)]


class TestConstruction(unittest.TestCase):
    def test_empty_has_no_interval(self):
        self.assertEqual(IntervalSet().count(), 0)

    def test_items_are_copied(self):
        s = IntervalSet(SAMPLE)
        s.intervals.append((99, 100))
        self.assertEqual(s.count(), 5)

    def test_reversed_endpoints(self):
        with self.assertRaises(IntervalErro):
            IntervalSet([(5, 1)])

    def test_bad_arity(self):
        with self.assertRaises(IntervalErro):
            IntervalSet([(1,)])

    def test_non_integer_endpoint(self):
        with self.assertRaises(IntervalErro):
            IntervalSet([(1, "a")])

    def test_bool_is_not_integer(self):
        with self.assertRaises(IntervalErro):
            IntervalSet([(True, 2)])

    def test_not_a_sequence(self):
        with self.assertRaises(IntervalErro):
            IntervalSet("abc")

    def test_point_interval_is_ok(self):
        self.assertEqual(IntervalSet([(3, 3)]).count(), 1)


class TestMerge(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(IntervalSet().merge(), [])

    def test_single(self):
        self.assertEqual(IntervalSet([(2, 5)]).merge(), [(2, 5)])

    def test_touching_merge(self):
        self.assertEqual(IntervalSet([(1, 3), (3, 5)]).merge(), [(1, 5)])

    def test_disjoint_kept(self):
        self.assertEqual(IntervalSet([(1, 2), (5, 6)]).merge(), [(1, 2), (5, 6)])

    def test_contained_swallowed(self):
        self.assertEqual(IntervalSet([(1, 10), (2, 3)]).merge(), [(1, 10)])

    def test_full_overlap_single(self):
        self.assertEqual(IntervalSet([(1, 5), (2, 6), (3, 7)]).merge(), [(1, 7)])

    def test_duplicate_collapses(self):
        self.assertEqual(IntervalSet([(1, 2), (1, 2), (1, 2)]).merge(), [(1, 2)])

    def test_negative_endpoints(self):
        self.assertEqual(IntervalSet([(-5, -1), (-3, 2)]).merge(), [(-5, 2)])

    def test_point_and_range(self):
        self.assertEqual(IntervalSet([(3, 3), (1, 5)]).merge(), [(1, 5)])

    def test_sample(self):
        self.assertEqual(
            IntervalSet(SAMPLE).merge(), [(1, 6), (8, 12), (20, 21)]
        )


class TestIntersection(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(IntervalSet().intersection(), [])

    def test_single_has_no_pair(self):
        self.assertEqual(IntervalSet([(1, 5)]).intersection(), [])

    def test_disjoint(self):
        self.assertEqual(IntervalSet([(1, 2), (5, 6)]).intersection(), [])

    def test_point_overlap(self):
        self.assertEqual(IntervalSet([(1, 3), (3, 5)]).intersection(), [(3, 3)])

    def test_containment(self):
        self.assertEqual(IntervalSet([(1, 10), (2, 3)]).intersection(), [(2, 3)])

    def test_duplicate_pair(self):
        self.assertEqual(
            IntervalSet([(1, 2), (1, 2)]).intersection(), [(1, 2)]
        )

    def test_sample(self):
        self.assertEqual(
            IntervalSet(SAMPLE).intersection(), [(2, 4), (9, 10)]
        )


class TestCoverage(unittest.TestCase):
    def test_empty_length(self):
        self.assertEqual(IntervalSet().coverage_length(), 0)

    def test_point_length_zero(self):
        self.assertEqual(IntervalSet([(3, 3)]).coverage_length(), 0)

    def test_union_length_matches(self):
        s = IntervalSet(SAMPLE)
        self.assertEqual(s.union_length(), s.coverage_length())

    def test_sample_length(self):
        self.assertEqual(IntervalSet(SAMPLE).coverage_length(), 10)

    def test_duplicate_length_not_doubled(self):
        self.assertEqual(IntervalSet([(1, 2), (1, 2), (1, 2)]).coverage_length(), 1)

    def test_negative_length(self):
        self.assertEqual(IntervalSet([(-5, -1), (-3, 2)]).coverage_length(), 7)

    def test_contained_length(self):
        self.assertEqual(IntervalSet([(1, 10), (2, 3)]).coverage_length(), 9)

    def test_cover_point_hits(self):
        self.assertEqual(IntervalSet(SAMPLE).covers_point(9), [2, 3])

    def test_cover_point_none(self):
        self.assertEqual(IntervalSet(SAMPLE).covers_point(7), [])

    def test_coverage_count(self):
        self.assertEqual(IntervalSet(SAMPLE).coverage_count(3), 2)

    def test_is_covered(self):
        s = IntervalSet(SAMPLE)
        self.assertTrue(s.is_covered(1))
        self.assertTrue(s.is_covered(21))
        self.assertFalse(s.is_covered(7))

    def test_bad_point(self):
        with self.assertRaises(IntervalErro):
            IntervalSet(SAMPLE).covers_point("a")


class TestMaxOverlap(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(IntervalSet().max_overlap(), 0)

    def test_single(self):
        self.assertEqual(IntervalSet([(2, 5)]).max_overlap(), 1)

    def test_disjoint(self):
        self.assertEqual(IntervalSet([(1, 2), (5, 6)]).max_overlap(), 1)

    def test_duplicate_triple(self):
        self.assertEqual(IntervalSet([(1, 2), (1, 2), (1, 2)]).max_overlap(), 3)

    def test_point_intervals(self):
        self.assertEqual(IntervalSet([(3, 3), (3, 3)]).max_overlap(), 2)

    def test_containment(self):
        self.assertEqual(IntervalSet([(1, 10), (2, 3)]).max_overlap(), 2)

    def test_negative(self):
        self.assertEqual(IntervalSet([(-5, -1), (-3, 2)]).max_overlap(), 2)

    def test_sample(self):
        self.assertEqual(IntervalSet(SAMPLE).max_overlap(), 2)


class TestContainment(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(IntervalSet().containment(), [])

    def test_single(self):
        self.assertEqual(IntervalSet([(1, 5)]).containment(), [])

    def test_disjoint(self):
        self.assertEqual(IntervalSet([(1, 2), (5, 6)]).containment(), [])

    def test_nested_chain(self):
        s = IntervalSet([(1, 10), (2, 5), (3, 4), (20, 25)])
        self.assertEqual(s.containment(), [(1, 0), (2, 0), (2, 1)])

    def test_pair_relation(self):
        s = IntervalSet([(1, 10), (2, 5), (3, 4), (20, 25)])
        self.assertEqual(s.contains_pair(2, 0), (True, False))
        self.assertEqual(s.contains_pair(0, 2), (False, True))
        self.assertEqual(s.contains_pair(0, 3), (False, False))

    def test_equal_intervals_both_ways(self):
        s = IntervalSet([(1, 2), (1, 2)])
        self.assertEqual(s.contains_pair(0, 1), (True, True))

    def test_index_out_of_range(self):
        with self.assertRaises(IndexErro):
            IntervalSet(SAMPLE).contains_pair(0, 9)

    def test_index_not_integer(self):
        with self.assertRaises(IndexErro):
            IntervalSet(SAMPLE).contains_pair("a", 0)


class TestCoverWith(unittest.TestCase):
    def test_basic_chain(self):
        s = IntervalSet([(1, 4), (2, 8), (6, 12), (9, 15)])
        self.assertEqual(s.cover_with((1, 15)), [0, 1, 2, 3])

    def test_tie_takes_smaller_index(self):
        s = IntervalSet([(1, 10), (1, 10)])
        self.assertEqual(s.cover_with((1, 10)), [0])

    def test_point_target(self):
        s = IntervalSet([(1, 5), (3, 3)])
        self.assertEqual(s.cover_with((3, 3)), [0])

    def test_point_target_uncovered(self):
        s = IntervalSet([(1, 5)])
        self.assertEqual(s.cover_with((9, 9)), [])

    def test_gap_is_unreachable(self):
        s = IntervalSet([(1, 2), (5, 6)])
        self.assertEqual(s.cover_with((1, 6)), [])

    def test_whole_target_single(self):
        s = IntervalSet([(1, 10), (2, 3)])
        self.assertEqual(s.cover_with((1, 10)), [0])

    def test_negative_target(self):
        s = IntervalSet([(-5, 0), (-1, 4)])
        self.assertEqual(s.cover_with((-5, 4)), [0, 1])

    def test_empty_set(self):
        self.assertEqual(IntervalSet().cover_with((1, 5)), [])

    def test_bad_target(self):
        with self.assertRaises(TargetErro):
            IntervalSet(SAMPLE).cover_with((5, 1))

    def test_bad_target_arity(self):
        with self.assertRaises(TargetErro):
            IntervalSet(SAMPLE).cover_with((1,))


class TestSolveAll(unittest.TestCase):
    def test_bundle(self):
        s = IntervalSet([(1, 4), (2, 8), (6, 12), (9, 15)])
        got = s.solve_all((1, 15))
        self.assertEqual(got["merged"], [(1, 15)])
        self.assertEqual(got["union_length"], 14)
        self.assertEqual(got["cover"], [0, 1, 2, 3])
        self.assertEqual(got["intersection"], [(2, 4), (6, 8), (9, 12)])


class TestIndependentPaths(unittest.TestCase):
    def test_merge_matches(self):
        cases = [
            SAMPLE,
            [],
            [(1, 2), (5, 6)],
            [(1, 10), (2, 3)],
            [(-5, -1), (-3, 2)],
            [(3, 3), (3, 3)],
        ]
        for case in cases:
            s = IntervalSet(case)
            self.assertEqual(s.independent_brute_merge(), s.merge(), repr(case))

    def test_max_overlap_matches(self):
        cases = [
            SAMPLE,
            [],
            [(1, 2), (1, 2), (1, 2)],
            [(1, 10), (2, 3)],
            [(-5, -1), (-3, 2)],
            [(3, 3), (3, 3)],
        ]
        for case in cases:
            s = IntervalSet(case)
            self.assertEqual(
                s.independent_brute_max_overlap(), s.max_overlap(), repr(case)
            )

    def test_max_overlap_agrees_with_points(self):
        s = IntervalSet([(1, 5), (2, 3), (4, 7)])
        best = 0
        for p in range(1, 8):
            c = s.coverage_count(p)
            if c > best:
                best = c
        self.assertEqual(best, s.max_overlap())


class TestScaleMetrics(unittest.TestCase):
    def test_comparison_count_positive(self):
        s = IntervalSet(SAMPLE)
        self.assertEqual(s.comparison_count(), 5 * 4 + 5 * 5)

    def test_access_count_positive(self):
        s = IntervalSet(SAMPLE)
        self.assertEqual(s.access_count(), (21 - 1 + 1) * 5)

    def test_empty_metrics_zero(self):
        s = IntervalSet()
        self.assertEqual(s.comparison_count(), 0)
        self.assertEqual(s.access_count(), 0)

    def test_metrics_are_pure(self):
        s = IntervalSet(SAMPLE)
        self.assertEqual(s.comparison_count(), s.comparison_count())
        self.assertEqual(s.access_count(), s.access_count())


class TestDeterminism(unittest.TestCase):
    def test_repeated_merge(self):
        a = IntervalSet(SAMPLE).merge()
        b = IntervalSet(SAMPLE).merge()
        self.assertEqual(a, b)

    def test_two_paths_agree_repeatedly(self):
        s = IntervalSet(SAMPLE)
        self.assertEqual(s.independent_brute_merge(), s.independent_brute_merge())
        self.assertEqual(s.merge(), s.merge())

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(IntervalErro, Erro))
        self.assertTrue(issubclass(TargetErro, Erro))
        self.assertTrue(issubclass(IndexErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
