"""diffx 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：构造与校验、单点查询、区间加的闭区间语义、
前缀和与区间求和、离线重放、二维区域加、改动点计数、平局口径与异常层级。
改造时本文件一个字都不许改，新行为一律另开测试文件。
"""

import unittest

from diffx.array import (
    DiffArray,
    DiffError,
    DiffMatrix,
    InvalidIndexError,
    InvalidMatrixError,
    InvalidRangeError,
    InvalidShapesError,
    InvalidSizeError,
    elementwise_add,
    elementwise_equal,
    flatten,
)


class TestConstruction(unittest.TestCase):
    def test_size_and_values(self):
        arr = DiffArray([1, 2, 3])
        self.assertEqual(arr.size(), 3)
        self.assertEqual(len(arr), 3)
        self.assertEqual(arr.to_list(), [1, 2, 3])

    def test_zeros(self):
        arr = DiffArray.zeros(4)
        self.assertEqual(arr.to_list(), [0, 0, 0, 0])

    def test_zero_size_allowed(self):
        arr = DiffArray.zeros(0)
        self.assertEqual(arr.size(), 0)
        self.assertEqual(arr.to_list(), [])

    def test_to_list_returns_copy(self):
        arr = DiffArray([1, 2, 3])
        got = arr.to_list()
        got.append(99)
        self.assertEqual(arr.size(), 3)

    def test_negative_size_raises(self):
        with self.assertRaises(InvalidSizeError):
            DiffArray.zeros(-1)

    def test_non_int_size_raises(self):
        with self.assertRaises(InvalidSizeError):
            DiffArray.zeros(2.5)

    def test_bool_size_raises(self):
        with self.assertRaises(InvalidSizeError):
            DiffArray.zeros(True)

    def test_non_number_element_raises(self):
        with self.assertRaises(InvalidSizeError):
            DiffArray([1, "x", 3])

    def test_bool_element_raises(self):
        with self.assertRaises(InvalidSizeError):
            DiffArray([1, True, 3])


class TestValueAt(unittest.TestCase):
    def test_basic(self):
        arr = DiffArray([10, 20, 30])
        self.assertEqual(arr.value_at(0), 10)
        self.assertEqual(arr.value_at(2), 30)

    def test_out_of_range_raises(self):
        arr = DiffArray([10, 20, 30])
        with self.assertRaises(InvalidIndexError):
            arr.value_at(3)

    def test_negative_raises(self):
        arr = DiffArray([10, 20, 30])
        with self.assertRaises(InvalidIndexError):
            arr.value_at(-1)

    def test_bool_index_raises(self):
        arr = DiffArray([10, 20, 30])
        with self.assertRaises(InvalidIndexError):
            arr.value_at(True)

    def test_empty_raises(self):
        with self.assertRaises(InvalidIndexError):
            DiffArray.zeros(0).value_at(0)


class TestRangeAdd(unittest.TestCase):
    def test_single_position(self):
        arr = DiffArray([0, 0, 0, 0])
        arr.range_add(1, 1, 5)
        self.assertEqual(arr.to_list(), [0, 5, 0, 0])

    def test_closed_interval(self):
        arr = DiffArray([0, 0, 0, 0, 0])
        arr.range_add(1, 3, 2)
        self.assertEqual(arr.to_list(), [0, 2, 2, 2, 0])

    def test_whole_array(self):
        arr = DiffArray([1, 2, 3])
        arr.range_add(0, 2, 10)
        self.assertEqual(arr.to_list(), [11, 12, 13])

    def test_negative_delta(self):
        arr = DiffArray([5, 5, 5])
        arr.range_add(0, 1, -3)
        self.assertEqual(arr.to_list(), [2, 2, 5])

    def test_left_greater_than_right_raises(self):
        arr = DiffArray([0, 0, 0])
        with self.assertRaises(InvalidRangeError):
            arr.range_add(2, 1, 1)

    def test_out_of_range_raises(self):
        arr = DiffArray([0, 0, 0])
        with self.assertRaises(InvalidRangeError):
            arr.range_add(1, 3, 1)

    def test_negative_left_raises(self):
        arr = DiffArray([0, 0, 0])
        with self.assertRaises(InvalidRangeError):
            arr.range_add(-1, 1, 1)

    def test_non_number_delta_raises(self):
        arr = DiffArray([0, 0, 0])
        with self.assertRaises(InvalidRangeError):
            arr.range_add(0, 1, "x")

    def test_empty_array_raises(self):
        arr = DiffArray.zeros(0)
        with self.assertRaises(InvalidRangeError):
            arr.range_add(0, 0, 1)


class TestPrefixSum(unittest.TestCase):
    def test_inclusive(self):
        arr = DiffArray([1, 2, 3, 4])
        self.assertEqual(arr.prefix_sum(0), 1)
        self.assertEqual(arr.prefix_sum(1), 3)
        self.assertEqual(arr.prefix_sum(3), 10)

    def test_after_range_add_matches_rescan(self):
        arr = DiffArray([0, 0, 0, 0])
        arr.range_add(1, 2, 4)
        self.assertEqual(arr.prefix_sum(3), 8)
        self.assertEqual(arr.to_list(), [0, 4, 4, 0])

    def test_out_of_range_raises(self):
        arr = DiffArray([1, 2, 3])
        with self.assertRaises(InvalidIndexError):
            arr.prefix_sum(3)


class TestRangeSum(unittest.TestCase):
    def test_basic(self):
        arr = DiffArray([1, 2, 3, 4])
        self.assertEqual(arr.range_sum(1, 2), 5)
        self.assertEqual(arr.range_sum(0, 3), 10)

    def test_single_element(self):
        arr = DiffArray([1, 2, 3, 4])
        self.assertEqual(arr.range_sum(2, 2), 3)

    def test_total_sum(self):
        arr = DiffArray([1, 2, 3, 4])
        self.assertEqual(arr.total_sum(), 10)

    def test_total_sum_empty_raises(self):
        with self.assertRaises(InvalidRangeError):
            DiffArray.zeros(0).total_sum()

    def test_left_greater_than_right_raises(self):
        arr = DiffArray([1, 2, 3])
        with self.assertRaises(InvalidRangeError):
            arr.range_sum(2, 1)

    def test_out_of_range_raises(self):
        arr = DiffArray([1, 2, 3])
        with self.assertRaises(InvalidRangeError):
            arr.range_sum(0, 3)


class TestReplay(unittest.TestCase):
    def test_replay_matches_sequential(self):
        operations = [(0, 2, 3), (1, 1, -1), (2, 2, 5)]
        replayed = DiffArray.zeros(3)
        self.assertEqual(replayed.replay(operations), [3, 2, 8])
        step = DiffArray.zeros(3)
        for left, right, delta in operations:
            step.range_add(left, right, delta)
        self.assertEqual(replayed.to_list(), step.to_list())

    def test_replay_zero_operations(self):
        arr = DiffArray([1, 2, 3])
        self.assertEqual(arr.replay([]), [1, 2, 3])

    def test_replay_resets_change_count(self):
        arr = DiffArray([0, 0, 0])
        arr.range_add(0, 2, 1)
        arr.replay([(0, 0, 7)])
        self.assertEqual(arr.change_count(), 1)
        self.assertEqual(arr.to_list(), [8, 1, 1])


class TestChangeCount(unittest.TestCase):
    def test_range_add_counts_elements(self):
        arr = DiffArray.zeros(4)
        arr.range_add(1, 3, 2)
        self.assertEqual(arr.change_count(), 3)

    def test_query_also_counts(self):
        arr = DiffArray([1, 2, 3])
        arr.range_sum(0, 2)
        self.assertEqual(arr.change_count(), 3)

    def test_reset(self):
        arr = DiffArray.zeros(4)
        arr.range_add(0, 3, 1)
        self.assertEqual(arr.change_count(), 4)
        arr.reset_change_count()
        self.assertEqual(arr.change_count(), 0)


class TestMatrix(unittest.TestCase):
    def test_zeros_and_shape(self):
        matrix = DiffMatrix.zeros(2, 3)
        self.assertEqual(matrix.shape(), (2, 3))
        self.assertEqual(matrix.values(), [[0, 0, 0], [0, 0, 0]])

    def test_value_at(self):
        matrix = DiffMatrix([[1, 2], [3, 4]])
        self.assertEqual(matrix.value_at(1, 0), 3)

    def test_value_at_out_of_range_raises(self):
        matrix = DiffMatrix([[1, 2], [3, 4]])
        with self.assertRaises(InvalidIndexError):
            matrix.value_at(2, 0)

    def test_region_add(self):
        matrix = DiffMatrix.zeros(3, 3)
        matrix.region_add(0, 1, 1, 2, 5)
        self.assertEqual(matrix.values(), [[0, 5, 5], [0, 5, 5], [0, 0, 0]])

    def test_region_add_single_cell(self):
        matrix = DiffMatrix.zeros(2, 2)
        matrix.region_add(1, 1, 1, 1, 4)
        self.assertEqual(matrix.values(), [[0, 0], [0, 4]])

    def test_region_add_inverted_raises(self):
        matrix = DiffMatrix.zeros(3, 3)
        with self.assertRaises(InvalidRangeError):
            matrix.region_add(2, 0, 1, 2, 1)

    def test_region_add_out_of_range_raises(self):
        matrix = DiffMatrix.zeros(2, 2)
        with self.assertRaises(InvalidRangeError):
            matrix.region_add(0, 0, 2, 1, 1)

    def test_region_add_change_count(self):
        matrix = DiffMatrix.zeros(3, 3)
        matrix.region_add(0, 0, 1, 1, 1)
        self.assertEqual(matrix.change_count(), 4)

    def test_empty_matrix_raises(self):
        with self.assertRaises(InvalidMatrixError):
            DiffMatrix([])

    def test_ragged_matrix_raises(self):
        with self.assertRaises(InvalidMatrixError):
            DiffMatrix([[1, 2], [3]])

    def test_non_number_cell_raises(self):
        with self.assertRaises(InvalidMatrixError):
            DiffMatrix([[1, "x"]])

    def test_negative_shape_raises(self):
        with self.assertRaises(InvalidSizeError):
            DiffMatrix.zeros(0, 3)


class TestHelpers(unittest.TestCase):
    def test_flatten(self):
        self.assertEqual(flatten([[1, 2], [3, 4]]), [1, 2, 3, 4])

    def test_elementwise_add_list(self):
        self.assertEqual(elementwise_add([1, 2], [3, 4]), [4, 6])

    def test_elementwise_add_shape_mismatch_raises(self):
        with self.assertRaises(InvalidShapesError):
            elementwise_add([1, 2], [3, 4, 5])

    def test_elementwise_add_matrix(self):
        a = DiffMatrix([[1, 2], [3, 4]])
        b = DiffMatrix([[10, 20], [30, 40]])
        self.assertEqual(elementwise_add(a, b), [[11, 22], [33, 44]])

    def test_elementwise_add_matrix_shape_mismatch_raises(self):
        a = DiffMatrix([[1, 2]])
        b = DiffMatrix([[1, 2, 3]])
        with self.assertRaises(InvalidShapesError):
            elementwise_add(a, b)

    def test_elementwise_equal_true(self):
        self.assertTrue(elementwise_equal([1, 2, 3], [1, 2, 3]))

    def test_elementwise_equal_false(self):
        self.assertFalse(elementwise_equal([1, 2, 3], [1, 2, 4]))

    def test_elementwise_equal_shape_mismatch_raises(self):
        with self.assertRaises(InvalidShapesError):
            elementwise_equal([1, 2], [1, 2, 3])


class TestDeterminism(unittest.TestCase):
    def test_sequence_repeatable(self):
        def run():
            arr = DiffArray.zeros(5)
            arr.range_add(1, 3, 2)
            arr.range_add(2, 4, -1)
            return arr.to_list()
        self.assertEqual(run(), run())

    def test_no_shared_state_between_instances(self):
        a = DiffArray([1, 2, 3])
        b = DiffArray.zeros(3)
        a.range_add(0, 2, 5)
        self.assertEqual(b.to_list(), [0, 0, 0])
        self.assertEqual(a.to_list(), [6, 7, 8])


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (InvalidSizeError, InvalidIndexError, InvalidRangeError,
                    InvalidMatrixError, InvalidShapesError):
            self.assertTrue(issubclass(exc, DiffError))

    def test_catchable_via_base(self):
        with self.assertRaises(DiffError):
            DiffArray.zeros(3).value_at(9)


if __name__ == "__main__":
    unittest.main()
