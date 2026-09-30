"""基线测试：锁住改造前 circlp.circular.CircularOpt 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - brute_max_sum 枚举断点拆环再对每条链指数枚举互不相邻子集；
  - brute_max_segment 枚举断点拆环后平方枚举全部连续子段；
  - brute_best_partition 枚举断点拆环后枚举全部断点组合；
  - brute_plan 给出最优选取下标集合，并列时按下标序列字典序最小；
  - brute_diff_sum 与 brute_min_delete 是指定的两项独立能力；
  - independent_split 与 independent_minus 是两条独立慢速做法，与主路径对账。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circlp.circular import (  # noqa: E402
    CircularOpt,
    Erro,
    ValueErro,
    IndexErro,
    ChooseErro,
    MAX_ENUM_LEN,
)


class TestConstruction(unittest.TestCase):
    def test_size(self):
        self.assertEqual(CircularOpt([1, 2, 3]).size, 3)

    def test_values_copy(self):
        c = CircularOpt([1, 2, 3])
        self.assertEqual(c.values, [1, 2, 3])

    def test_empty_ok(self):
        self.assertEqual(CircularOpt([]).size, 0)

    def test_non_sequence(self):
        with self.assertRaises(ValueErro):
            CircularOpt(5)

    def test_string_rejected(self):
        with self.assertRaises(ValueErro):
            CircularOpt("123")

    def test_nonnumeric_element(self):
        with self.assertRaises(ValueErro):
            CircularOpt([1, "a", 3])

    def test_bool_rejected(self):
        with self.assertRaises(ValueErro):
            CircularOpt([1, True])


class TestMaxSum(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(CircularOpt([]).brute_max_sum(), 0)

    def test_single_positive(self):
        self.assertEqual(CircularOpt([5]).brute_max_sum(), 5)

    def test_single_negative(self):
        self.assertEqual(CircularOpt([-5]).brute_max_sum(), 0)

    def test_two_elements(self):
        self.assertEqual(CircularOpt([3, 5]).brute_max_sum(), 5)

    def test_all_positive_ring(self):
        # 首尾相邻，[5,1,1,5] 的两个 5 互为邻居不能同取，取一个 5 加一个 1。
        self.assertEqual(CircularOpt([5, 1, 1, 5]).brute_max_sum(), 6)

    def test_classic_house_robber_ring(self):
        self.assertEqual(CircularOpt([2, 3, 2]).brute_max_sum(), 3)

    def test_longer(self):
        self.assertEqual(CircularOpt([1, 2, 3, 1]).brute_max_sum(), 4)

    def test_all_negative(self):
        self.assertEqual(CircularOpt([-2, -3, -1]).brute_max_sum(), 0)

    def test_with_zero(self):
        self.assertEqual(CircularOpt([0, -1, 0]).brute_max_sum(), 0)


class TestMaxSegment(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(CircularOpt([]).brute_max_segment(), 0)

    def test_all_positive_wraps(self):
        # 环上整段可跨界，[1,2,3] 取全段为 6。
        self.assertEqual(CircularOpt([1, 2, 3]).brute_max_segment(), 6)

    def test_classic_ring(self):
        self.assertEqual(CircularOpt([5, -3, 5]).brute_max_segment(), 10)

    def test_all_negative(self):
        self.assertEqual(CircularOpt([-1, -2, -3]).brute_max_segment(), 0)

    def test_single(self):
        self.assertEqual(CircularOpt([7]).brute_max_segment(), 7)

    def test_mixed(self):
        self.assertEqual(CircularOpt([-2, 1, -3, 4, -1, 2, 1, -5, 4]).brute_max_segment(), 6)

    def test_zero_ring(self):
        self.assertEqual(CircularOpt([0, 0, 0]).brute_max_segment(), 0)


class TestPartition(unittest.TestCase):
    def test_one_part(self):
        self.assertEqual(CircularOpt([1, 2, 3, 4]).brute_best_partition(1), 10)

    def test_two_parts(self):
        self.assertEqual(CircularOpt([1, 2, 3, 4]).brute_best_partition(2), 5)

    def test_four_parts(self):
        self.assertEqual(CircularOpt([1, 2, 3, 4]).brute_best_partition(4), 4)

    def test_negative(self):
        self.assertEqual(CircularOpt([-1, -2, -3]).brute_best_partition(2), -3)

    def test_bad_parts_zero(self):
        with self.assertRaises(ChooseErro):
            CircularOpt([1, 2, 3]).brute_best_partition(0)

    def test_bad_parts_over(self):
        with self.assertRaises(ChooseErro):
            CircularOpt([1, 2, 3]).brute_best_partition(4)


class TestDiffSum(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(CircularOpt([]).brute_diff_sum(), 0)

    def test_single(self):
        self.assertEqual(CircularOpt([9]).brute_diff_sum(), 0)

    def test_two(self):
        # 环上两元素互为左右邻，取一个即同时占住首尾，按口径不选满首尾，只能空取。
        self.assertEqual(CircularOpt([1, 4]).brute_diff_sum(), 0)

    def test_ring(self):
        # 环 1 5 2 上系数依次为 5 减 2、2 减 1、1 减 5，即 3、1、-4，
        # 取位置零得 3 且未同时占首尾，最大为 3。
        self.assertEqual(CircularOpt([1, 5, 2]).brute_diff_sum(), 3)

    def test_constant_ring(self):
        self.assertEqual(CircularOpt([3, 3, 3, 3]).brute_diff_sum(), 0)

    def test_not_negative(self):
        self.assertGreaterEqual(CircularOpt([4, 1, 3]).brute_diff_sum(), 0)


class TestMinDelete(unittest.TestCase):
    def test_zero_count(self):
        self.assertEqual(CircularOpt([1, 2, 3, 4]).brute_min_delete(0), 0)

    def test_empty_zero(self):
        self.assertEqual(CircularOpt([]).brute_min_delete(0), 0)

    def test_one_delete(self):
        self.assertEqual(CircularOpt([5, 1, 4, 2]).brute_min_delete(1), 1)

    def test_two_deletes(self):
        self.assertEqual(CircularOpt([5, 1, 4, 2, 3]).brute_min_delete(2), 3)

    def test_bad_count_negative(self):
        with self.assertRaises(ChooseErro):
            CircularOpt([1, 2, 3]).brute_min_delete(-1)

    def test_bad_count_over(self):
        with self.assertRaises(ChooseErro):
            CircularOpt([1, 2, 3, 4]).brute_min_delete(3)


class TestPlan(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(CircularOpt([]).brute_plan(), [])

    def test_classic_ring(self):
        self.assertEqual(CircularOpt([2, 3, 2]).brute_plan(), [1])

    def test_tie_takes_smallest_indices(self):
        # [1, 1, 1, 1] 环上半数最多取两互不相邻：{0,2} 与 {1,3}，
        # 并列时按下标序列字典序最小取 {0, 2}。
        self.assertEqual(CircularOpt([1, 1, 1, 1]).brute_plan(), [0, 2])

    def test_all_negative(self):
        self.assertEqual(CircularOpt([-1, -2]).brute_plan(), [])

    def test_head_tail_not_both(self):
        plan = CircularOpt([5, 1, 1, 5]).brute_plan()
        self.assertNotEqual(sorted(plan), [0, 3])
        self.assertTrue(set(plan).issubset({0, 1, 2, 3}))

    def test_sum_matches_plan(self):
        c = CircularOpt([3, 2, 5, 1, 4])
        plan = c.brute_plan()
        total = sum(c.values[i] for i in plan)
        self.assertEqual(total, c.brute_max_sum())

    def test_single_positive(self):
        self.assertEqual(CircularOpt([4]).brute_plan(), [0])


class TestIndependentPaths(unittest.TestCase):
    def test_split_matches_max_sum(self):
        cases = [
            [],
            [5],
            [-5],
            [3, 5],
            [2, 3, 2],
            [1, 2, 3, 1],
            [5, 1, 1, 5],
            [-2, -3, -1],
            [0, -1, 0],
            [7, -1, 4, -2, 6, -3, 2],
        ]
        for values in cases:
            c = CircularOpt(values)
            self.assertEqual(c.independent_split(), c.brute_max_sum(), repr(values))

    def test_split_matches_for_a_range(self):
        for n in range(0, 8):
            values = [((i * 7) % 11) - 5 for i in range(n)]
            c = CircularOpt(values)
            self.assertEqual(c.independent_split(), c.brute_max_sum(), repr(values))

    def test_minus_matches_max_segment(self):
        cases = [
            [],
            [1, 2, 3],
            [5, -3, 5],
            [-1, -2, -3],
            [7],
            [-2, 1, -3, 4, -1, 2, 1, -5, 4],
            [0, 0, 0],
            [3, 3, 3],
        ]
        for values in cases:
            c = CircularOpt(values)
            self.assertEqual(c.independent_minus(), c.brute_max_segment(), repr(values))

    def test_minus_matches_for_a_range(self):
        for n in range(0, 8):
            values = [((i * 5) % 9) - 4 for i in range(n)]
            c = CircularOpt(values)
            self.assertEqual(c.independent_minus(), c.brute_max_segment(), repr(values))


class TestScaleMetrics(unittest.TestCase):
    def test_break_trials_positive(self):
        c = CircularOpt([1, 2, 3, 4])
        c.brute_max_sum()
        self.assertGreater(c.break_trial_count, 0)

    def test_linear_steps_positive(self):
        c = CircularOpt([1, 2, 3, 4])
        c.independent_split()
        self.assertGreater(c.linear_step_count, 0)

    def test_minus_steps_positive(self):
        c = CircularOpt([1, 2, 3, 4])
        c.independent_minus()
        self.assertGreater(c.minus_step_count, 0)

    def test_fresh_instance_counts_zero(self):
        c = CircularOpt([1, 2, 3])
        self.assertEqual(c.break_trial_count, 0)
        self.assertEqual(c.linear_step_count, 0)
        self.assertEqual(c.minus_step_count, 0)

    def test_counts_reset_between_calls(self):
        c = CircularOpt([1, 2, 3, 4])
        c.brute_max_sum()
        first = c.break_trial_count
        c.brute_max_sum()
        self.assertEqual(c.break_trial_count, first)


class TestBoundsAndDeterminism(unittest.TestCase):
    def test_max_enum_len_ok(self):
        # 十八个一围成环，互不相邻最多取半数九个。
        c = CircularOpt([1] * MAX_ENUM_LEN)
        self.assertEqual(c.brute_max_sum(), MAX_ENUM_LEN // 2)

    def test_over_enum_len_rejected(self):
        c = CircularOpt([1] * (MAX_ENUM_LEN + 1))
        with self.assertRaises(ValueErro):
            c.brute_max_sum()

    def test_repeated_calls_agree(self):
        a = CircularOpt([3, 2, 5, 1, 4]).brute_plan()
        b = CircularOpt([3, 2, 5, 1, 4]).brute_plan()
        self.assertEqual(a, b)

    def test_two_paths_agree_repeatedly(self):
        c = CircularOpt([3, 2, 5, 1, 4])
        self.assertEqual(c.independent_split(), c.independent_split())

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(ValueErro, Erro))
        self.assertTrue(issubclass(IndexErro, Erro))
        self.assertTrue(issubclass(ChooseErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
