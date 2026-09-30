"""基线测试：锁住改造前 linbasis 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - max_xor 与 min_xor 枚举全部子集，在子集异或和里取极值；
  - xor_space_size 把全部子集异或和塞进集合去重后数个数；
  - kth_xor 把全部异或和排序去重后按下标取；
  - can_represent 枚举全部子集逐个比对，命中即真；
  - merge_spaces 把两组元素拼接后重新交给新的工具枚举。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linbasis.core import (  # noqa: E402
    InputErro,
    LinbasisErro,
    XorSpace,
)


class TestConstructionBaseline(unittest.TestCase):
    def test_numbers_kept_in_order(self):
        self.assertEqual(XorSpace([3, 5, 6]).numbers, (3, 5, 6))

    def test_duplicates_kept(self):
        self.assertEqual(XorSpace([1, 1, 1]).numbers, (1, 1, 1))

    def test_empty_allowed(self):
        self.assertEqual(XorSpace([]).numbers, ())

    def test_can_pass_iterator(self):
        self.assertEqual(XorSpace(iter([2, 4])).numbers, (2, 4))

    def test_none_raises(self):
        with self.assertRaises(InputErro):
            XorSpace(None)

    def test_negative_raises(self):
        with self.assertRaises(InputErro):
            XorSpace([-1])

    def test_bool_raises(self):
        with self.assertRaises(InputErro):
            XorSpace([True])

    def test_beyond_width_raises(self):
        with self.assertRaises(InputErro):
            XorSpace([1 << 64])


class TestExtremesBaseline(unittest.TestCase):
    def setUp(self):
        self.xs = XorSpace([3, 5, 6])

    def test_max_xor_of_rank_two_set(self):
        # 三五七这组里三与五异或得六，三者只有两个线性无关，最大异或和为六。
        self.assertEqual(self.xs.max_xor(), 6)

    def test_max_xor_of_independent_set(self):
        self.assertEqual(XorSpace([1, 2, 4]).max_xor(), 7)

    def test_min_xor_is_zero(self):
        self.assertEqual(self.xs.min_xor(), 0)

    def test_counters_reset_per_call(self):
        self.xs.max_xor()
        first = self.xs.subset_count
        self.xs.max_xor()
        self.assertEqual(self.xs.subset_count, first)

    def test_subset_count_is_power_of_two(self):
        self.xs.max_xor()
        self.assertEqual(self.xs.subset_count, 1 << len(self.xs.numbers))

    def test_empty_max_is_zero(self):
        self.assertEqual(XorSpace([]).max_xor(), 0)

    def test_empty_min_is_zero(self):
        self.assertEqual(XorSpace([]).min_xor(), 0)

    def test_all_same_identical_elems(self):
        # 单个重复元素，子集异或和非零即该值，最小值取零。
        xs = XorSpace([9, 9, 9])
        self.assertEqual(xs.max_xor(), 9)
        self.assertEqual(xs.min_xor(), 0)

    def test_single_element(self):
        self.assertEqual(XorSpace([5]).max_xor(), 5)
        self.assertEqual(XorSpace([5]).min_xor(), 0)

    def test_all_zero(self):
        xs = XorSpace([0, 0, 0])
        self.assertEqual(xs.max_xor(), 0)
        self.assertEqual(xs.min_xor(), 0)


class TestSpaceSizeBaseline(unittest.TestCase):
    def test_rank_two_gives_four(self):
        self.assertEqual(XorSpace([3, 5, 6]).xor_space_size(), 4)

    def test_three_independent_gives_eight(self):
        self.assertEqual(XorSpace([1, 2, 4]).xor_space_size(), 8)

    def test_empty_space_size_one(self):
        self.assertEqual(XorSpace([]).xor_space_size(), 1)

    def test_all_zero_space_size_one(self):
        self.assertEqual(XorSpace([0, 0, 0]).xor_space_size(), 1)

    def test_single_element_size_two(self):
        self.assertEqual(XorSpace([5]).xor_space_size(), 2)

    def test_duplicate_does_not_grow(self):
        self.assertEqual(XorSpace([7, 7, 7]).xor_space_size(), 2)


class TestKthBaseline(unittest.TestCase):
    def setUp(self):
        self.xs = XorSpace([3, 5, 6])

    def test_zeroth_is_min(self):
        self.assertEqual(self.xs.kth_xor(0), 0)

    def test_third_is_max(self):
        # 不同异或值只有零、三、五、六四个，升序末位是六。
        self.assertEqual(self.xs.kth_xor(3), 6)

    def test_second_value(self):
        self.assertEqual(self.xs.kth_xor(2), 5)

    def test_out_of_range_raises(self):
        with self.assertRaises(InputErro):
            self.xs.kth_xor(4)

    def test_negative_raises(self):
        with self.assertRaises(InputErro):
            self.xs.kth_xor(-1)

    def test_independent_set_kth(self):
        self.assertEqual(XorSpace([1, 2, 4]).kth_xor(5), 5)

    def test_empty_can_ask_kth_zero(self):
        self.assertEqual(XorSpace([]).kth_xor(0), 0)


class TestRepresentBaseline(unittest.TestCase):
    def setUp(self):
        self.xs = XorSpace([3, 5, 6])

    def test_represent_present(self):
        self.assertTrue(self.xs.can_represent(6))

    def test_represent_absent(self):
        self.assertFalse(self.xs.can_represent(7))

    def test_represent_zero_always(self):
        self.assertTrue(self.xs.can_represent(0))

    def test_negative_raises(self):
        with self.assertRaises(InputErro):
            self.xs.can_represent(-1)

    def test_empty_represents_only_zero(self):
        self.assertTrue(XorSpace([]).can_represent(0))
        self.assertFalse(XorSpace([]).can_represent(1))


class TestMergeBaseline(unittest.TestCase):
    def test_merge_keeps_all_numbers(self):
        merged = XorSpace([3, 5, 6]).merge_spaces([12])
        self.assertEqual(merged.numbers, (3, 5, 6, 12))

    def test_merge_takes_iterator(self):
        merged = XorSpace([1]).merge_spaces(iter([2]))
        self.assertEqual(merged.numbers, (1, 2))

    def test_merge_is_new_object(self):
        base = XorSpace([1])
        merged = base.merge_spaces([2])
        self.assertIsNot(merged, base)
        self.assertEqual(base.numbers, (1,))

    def test_merge_bad_input_raises(self):
        with self.assertRaises(InputErro):
            XorSpace([1]).merge_spaces(None)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        a = XorSpace([3, 5, 6])
        b = XorSpace([3, 5, 6])
        self.assertEqual(a.max_xor(), b.max_xor())
        self.assertEqual(a.xor_space_size(), b.xor_space_size())

    def test_no_shared_state_across_instances(self):
        a = XorSpace([1, 2])
        b = XorSpace([4, 8])
        a.max_xor()
        b.max_xor()
        self.assertNotEqual(a.numbers, b.numbers)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(InputErro, LinbasisErro))
        self.assertTrue(issubclass(LinbasisErro, Exception))


if __name__ == "__main__":
    unittest.main()
