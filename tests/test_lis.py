"""基线测试：锁住改造前 lisx.lis.LisKit 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - length 对每个位置向前枚举全部更小的位置，累加出最长上升子序列长度；
  - count 枚举全部子序列，逐个判定是否上升，把上升的计数；
  - rebuild 先算每个位置结尾的长度，再从尾部逐个回溯拼出一条方案；
  - 严格上升与非下降用两种口径分别判定。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lisx.lis import (  # noqa: E402
    LisKit,
    LisErro,
    SeqErro,
    ModeErro,
)


class TestLengthBaseline(unittest.TestCase):
    def setUp(self):
        self.k = LisKit()

    def test_empty_is_zero(self):
        self.assertEqual(self.k.length([]), 0)

    def test_single_is_one(self):
        self.assertEqual(self.k.length([7]), 1)

    def test_strict_increasing(self):
        self.assertEqual(self.k.length([1, 2, 3, 4]), 4)

    def test_strictly_decreasing_is_one(self):
        self.assertEqual(self.k.length([4, 3, 2, 1]), 1)

    def test_all_equal_strict_is_one(self):
        self.assertEqual(self.k.length([5, 5, 5]), 1)

    def test_classic_example(self):
        self.assertEqual(self.k.length([10, 9, 2, 5, 3, 7, 101, 18]), 4)

    def test_duplicate_strict_versus_nondecreasing(self):
        seq = [2, 2, 3, 3, 1]
        self.assertEqual(self.k.length(seq, "strict"), 2)
        self.assertEqual(self.k.length(seq, "nondecreasing"), 4)

    def test_all_equal_nondecreasing(self):
        self.assertEqual(self.k.length([5, 5, 5], "nondecreasing"), 3)

    def test_comparisons_positive(self):
        self.k.length([1, 2, 3, 4])
        self.assertGreater(self.k.comparisons, 0)

    def test_non_integer_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.length([1, ""])

    def test_float_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.length([1, 2.5, 3])

    def test_bool_is_not_int(self):
        with self.assertRaises(SeqErro):
            self.k.length([1, True, 3])

    def test_bad_mode_raises(self):
        with self.assertRaises(ModeErro):
            self.k.length([1, 2, 3], "either")

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SeqErro, LisErro))
        self.assertTrue(issubclass(ModeErro, LisErro))
        self.assertTrue(issubclass(LisErro, Exception))


class TestCountBaseline(unittest.TestCase):
    def setUp(self):
        self.k = LisKit()

    def test_empty_counts_one(self):
        self.assertEqual(self.k.count([]), 1)

    def test_single_counts_two(self):
        self.assertEqual(self.k.count([9]), 2)

    def test_strictly_increasing_counts_all_subsets(self):
        self.assertEqual(self.k.count([1, 2, 3]), 8)

    def test_strictly_decreasing_counts_distinct_singletons(self):
        self.assertEqual(self.k.count([3, 2, 1]), 4)

    def test_all_equal_strict_counts_empty_and_singletons(self):
        self.assertEqual(self.k.count([5, 5, 5]), 4)

    def test_all_equal_nondecreasing_counts_all_subsets(self):
        self.assertEqual(self.k.count([5, 5, 5], "nondecreasing"), 8)

    def test_duplicate_pair_strict(self):
        self.assertEqual(self.k.count([1, 1]), 3)

    def test_duplicate_pair_nondecreasing(self):
        self.assertEqual(self.k.count([1, 1], "nondecreasing"), 4)

    def test_classic_example_count(self):
        self.assertEqual(self.k.count([10, 9, 2, 5, 3, 7, 101, 18]), 42)

    def test_bad_mode_raises(self):
        with self.assertRaises(ModeErro):
            self.k.count([1, 2], "either")


class TestRebuildBaseline(unittest.TestCase):
    def setUp(self):
        self.k = LisKit()

    def _validate(self, seq, mode, order, vals):
        for a in range(1, len(order)):
            self.assertLess(order[a - 1], order[a])
        for a in range(1, len(vals)):
            if mode == "strict":
                self.assertLess(vals[a - 1], vals[a])
            else:
                self.assertLessEqual(vals[a - 1], vals[a])
        for i, v in zip(order, vals):
            self.assertEqual(seq[i], v)

    def test_empty_returns_empty(self):
        self.assertEqual(self.k.rebuild([]), ([], []))

    def test_single(self):
        self.assertEqual(self.k.rebuild([7]), ([0], [7]))

    def test_strictly_decreasing_singleton(self):
        self.assertEqual(self.k.rebuild([3, 2, 1]), ([2], [1]))

    def test_classic_example_length(self):
        seq = [10, 9, 2, 5, 3, 7, 101, 18]
        order, vals = self.k.rebuild(seq)
        self.assertEqual(len(order), self.k.length(seq))
        self._validate(seq, "strict", order, vals)

    def test_duplicate_nondecreasing_length(self):
        seq = [2, 2, 3, 3, 1]
        order, vals = self.k.rebuild(seq, "nondecreasing")
        self.assertEqual(len(order), 4)
        self._validate(seq, "nondecreasing", order, vals)

    def test_rebuild_matches_length(self):
        seq = [3, 1, 4, 1, 5, 9, 2, 6]
        order, vals = self.k.rebuild(seq)
        self.assertEqual(len(order), self.k.length(seq))
        self._validate(seq, "strict", order, vals)

    def test_rebuild_comparisons_positive(self):
        self.k.rebuild([1, 2, 3, 4])
        self.assertGreater(self.k.rebuild_comparisons, 0)

    def test_bad_mode_raises(self):
        with self.assertRaises(ModeErro):
            self.k.rebuild([1, 2], "either")


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        seq = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
        k1 = LisKit()
        k2 = LisKit()
        self.assertEqual(k1.length(seq), k2.length(seq))
        self.assertEqual(k1.count(seq), k2.count(seq))
        self.assertEqual(k1.rebuild(seq), k2.rebuild(seq))

    def test_counts_reset_between_calls(self):
        k = LisKit()
        seq = [1, 3, 2, 4]
        k.length(seq)
        first = k.comparisons
        k.length(seq)
        self.assertEqual(k.comparisons, first)

    def test_fresh_instance_has_zero_counts(self):
        k = LisKit()
        self.assertEqual(k.comparisons, 0)
        self.assertEqual(k.rebuild_comparisons, 0)


if __name__ == "__main__":
    unittest.main()
