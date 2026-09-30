"""fracprog 现有行为的锁定测试：入口校验、元素归一、朴素枚举取最优比率、恰好 k 个
的最优、带依赖的选取最优、可达性判定与枚举组合计数。

只覆盖当前朴素实现已经给出的结果，后面新增的二分答案加可行性判定路、动态规划或贪
心路以及两个独立能力、二分判定次数的规模对照都另开文件。
"""

import unittest
from fractions import Fraction

from fracprog import (
    Erro,
    RatioError,
    Tool,
    best_selection,
    best_selection_k,
    best_selection_with_deps,
    combination_count,
    is_reachable,
    naive_ratio,
    normalize_items,
    to_fraction,
)

ITEMS = [(2, 1), (3, 1), (1, 1)]


class TestParsing(unittest.TestCase):
    def test_to_fraction_accepts_int_and_fraction(self):
        self.assertEqual(to_fraction(3), Fraction(3))
        self.assertEqual(to_fraction(Fraction(1, 3)), Fraction(1, 3))

    def test_bool_rejected(self):
        with self.assertRaises(RatioError):
            to_fraction(True)

    def test_unknown_type_rejected(self):
        with self.assertRaises(RatioError):
            to_fraction("nope")


class TestNormalize(unittest.TestCase):
    def test_pairs_become_fractions(self):
        self.assertEqual(normalize_items([(2, 4), (3, 1)]),
                         [(Fraction(2), Fraction(4)), (Fraction(3), Fraction(1))])

    def test_empty_is_valid(self):
        self.assertEqual(normalize_items([]), [])

    def test_none_rejected(self):
        with self.assertRaises(RatioError):
            normalize_items(None)

    def test_both_zero_rejected(self):
        with self.assertRaises(RatioError):
            normalize_items([(0, 0)])

    def test_bad_pair_rejected(self):
        with self.assertRaises(RatioError):
            normalize_items([(1, 2, 3)])

    def test_negative_values_accepted(self):
        self.assertEqual(normalize_items([(-1, 2)]), [(Fraction(-1), Fraction(2))])


class TestRatio(unittest.TestCase):
    def test_ratio_of_sums(self):
        self.assertEqual(naive_ratio(7, 2), Fraction(7, 2))

    def test_zero_cost_rejected(self):
        with self.assertRaises(RatioError):
            naive_ratio(1, 0)

    def test_negative_cost_allowed(self):
        self.assertEqual(naive_ratio(1, -1), Fraction(-1))


class TestBestSelection(unittest.TestCase):
    def test_single_best_item(self):
        result = best_selection(ITEMS)
        self.assertEqual(result["ratio"], Fraction(3))
        self.assertEqual(result["selection"], [1])
        self.assertEqual(result["count"], 8)

    def test_single_can_beat_pair(self):
        # 单元素 2 的比值高过两元素合并的 5/3，最优应取单元素
        result = best_selection([(2, 1), (3, 2)])
        self.assertEqual(result["ratio"], Fraction(2))
        self.assertEqual(result["selection"], [0])

    def test_empty_items_give_zero(self):
        result = best_selection([])
        self.assertEqual(result["ratio"], Fraction(0))
        self.assertEqual(result["selection"], [])
        self.assertEqual(result["count"], 1)


class TestBestSelectionK(unittest.TestCase):
    def test_exactly_two(self):
        result = best_selection_k(ITEMS, 2)
        self.assertEqual(result["ratio"], Fraction(5, 2))
        self.assertEqual(result["selection"], [0, 1])

    def test_exactly_three(self):
        result = best_selection_k(ITEMS, 3)
        self.assertEqual(result["ratio"], Fraction(2))
        self.assertEqual(result["selection"], [0, 1, 2])

    def test_k_zero_gives_zero(self):
        result = best_selection_k(ITEMS, 0)
        self.assertEqual(result["ratio"], Fraction(0))
        self.assertEqual(result["selection"], [])
        self.assertEqual(result["count"], 8)

    def test_k_larger_than_count_rejected(self):
        with self.assertRaises(RatioError):
            best_selection_k(ITEMS, 4)

    def test_negative_k_rejected(self):
        with self.assertRaises(RatioError):
            best_selection_k(ITEMS, -1)


class TestDependencies(unittest.TestCase):
    def test_dependency_forces_prerequisite(self):
        result = best_selection_with_deps([(1, 1), (5, 1)], [None, 0])
        self.assertEqual(result["ratio"], Fraction(3))
        self.assertEqual(result["selection"], [0, 1])

    def test_empty_dependency_matches_free_choice(self):
        dep = [None, None, None]
        self.assertEqual(best_selection_with_deps(ITEMS, dep)["ratio"],
                         best_selection(ITEMS)["ratio"])

    def test_cycle_rejected(self):
        with self.assertRaises(RatioError):
            best_selection_with_deps(ITEMS, [1, 0, None])

    def test_out_of_range_rejected(self):
        with self.assertRaises(RatioError):
            best_selection_with_deps(ITEMS, [None, 9, None])

    def test_wrong_length_rejected(self):
        with self.assertRaises(RatioError):
            best_selection_with_deps(ITEMS, [None, 0])


class TestReachable(unittest.TestCase):
    def test_exact_optimum_is_reachable(self):
        self.assertTrue(is_reachable(ITEMS, Fraction(3))["reachable"])

    def test_above_optimum_is_unreachable(self):
        self.assertFalse(is_reachable(ITEMS, Fraction(4))["reachable"])

    def test_bad_target_rejected(self):
        with self.assertRaises(RatioError):
            is_reachable(ITEMS, "high")


class TestCombinationCount(unittest.TestCase):
    def test_power_of_two(self):
        self.assertEqual(combination_count(0), 1)
        self.assertEqual(combination_count(4), 16)

    def test_negative_rejected(self):
        with self.assertRaises(RatioError):
            combination_count(-1)

    def test_bool_rejected(self):
        with self.assertRaises(RatioError):
            combination_count(True)


class TestTool(unittest.TestCase):
    def test_count_accumulates_and_resets(self):
        tool = Tool(ITEMS)
        self.assertEqual(tool.enumeration_count(), 0)
        tool.best_selection()
        self.assertEqual(tool.enumeration_count(), 8)
        tool.reset_count()
        self.assertEqual(tool.enumeration_count(), 0)

    def test_tools_do_not_share_state(self):
        first = Tool(ITEMS)
        second = Tool(ITEMS)
        first.best_selection()
        self.assertEqual(second.enumeration_count(), 0)

    def test_repeat_run_is_stable(self):
        tool = Tool(ITEMS)
        self.assertEqual(tool.best_selection(), tool.best_selection())

    def test_methods_expose_ratio_and_selection(self):
        tool = Tool(ITEMS)
        self.assertEqual(tool.best_selection_k(2),
                         {"ratio": Fraction(5, 2), "selection": [0, 1]})
        self.assertTrue(tool.is_reachable(Fraction(2)))

    def test_error_base_class(self):
        self.assertTrue(issubclass(RatioError, Erro))


if __name__ == "__main__":
    unittest.main()
