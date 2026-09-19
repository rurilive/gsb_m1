"""skiplist 语义测试：以 README「语义约定」为唯一行为标准。

红用例（源码与 README 不符）上方均注释「README 期望 / 实际发生」。
所有用例确定性可重复：涉及随机层级的地方一律显式传 seed。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v
    python3 tests/test_skiplist.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skiplist.skiplist import SkipList


class TestInsertAndFind(unittest.TestCase):
    """README 第 1、3 条：insert 恒新增副本；find/in 命中任一副本，find 取最旧。"""

    def test_find_returns_value(self):
        sl = SkipList(seed=1)
        sl.insert(10, "a")
        self.assertEqual(sl.find(10), "a")

    def test_find_missing_returns_none(self):
        sl = SkipList(seed=1)
        sl.insert(10, "a")
        self.assertIsNone(sl.find(999))

    def test_contains_missing_is_false(self):
        sl = SkipList(seed=1)
        sl.insert(10, "a")
        self.assertNotIn(999, sl)

    def test_find_returns_oldest_copy_value(self):
        # README 第 3 条：find 返回最旧副本的 value。
        sl = SkipList(seed=1)
        sl.insert(5, "first")
        sl.insert(5, "second")
        self.assertEqual(sl.find(5), "first")

    def test_duplicate_copies_coexist_in_insertion_order(self):
        # 【红】README 第 1 条：insert 恒新增一个副本，同键副本按插入先后共存，
        # 先插的在前；range_scan 应输出两个副本 ("a" 在前、"b" 在后)。
        # 实际：第二个副本根本没接进链（_splice 遇到同键前驱直接跳过），
        # range_scan 只输出 [(5, "a")]。
        sl = SkipList(seed=1)
        sl.insert(5, "a")
        sl.insert(5, "b")
        self.assertEqual(sl.range_scan(), [(5, "a"), (5, "b")])

    def test_contains_with_none_value(self):
        # 【红】README 第 3 条：存在任一副本即命中（in 与 value 无关，
        # README 约定 value 任意，None 也是合法 value）。
        # 实际：__contains__ 用 find(...) is not None 判断，
        # value 为 None 的键被误判为不存在。
        sl = SkipList(seed=1)
        sl.insert(7, None)
        self.assertIn(7, sl)


class TestRemove(unittest.TestCase):
    """README 第 2 条：remove 恰移除最旧副本；无副本返回 False 且不改结构。"""

    def test_remove_present_returns_true(self):
        sl = SkipList(seed=1)
        sl.insert(3, "x")
        self.assertTrue(sl.remove(3))

    def test_remove_absent_returns_false_and_keeps_structure(self):
        sl = SkipList(seed=1)
        sl.insert(3, "x")
        before = sl.range_scan()
        self.assertFalse(sl.remove(999))
        self.assertEqual(sl.range_scan(), before)
        self.assertEqual(len(sl), 1)

    def test_remove_empty_returns_false(self):
        sl = SkipList(seed=1)
        self.assertFalse(sl.remove(1))
        self.assertEqual(len(sl), 0)

    def test_remove_last_copy_clears_contains(self):
        # 【红】README 第 2 条：移除之后该键若已无副本，__contains__ 必须为 False。
        # 实际：remove 只摘了 1 层以上的指针，漏摘第 0 层，
        # 节点仍挂在底层链上，in 依旧命中（删掉的键又冒出来）。
        sl = SkipList(seed=1)
        sl.insert(3, "x")
        self.assertTrue(sl.remove(3))
        self.assertNotIn(3, sl)

    def test_remove_last_copy_clears_range_scan(self):
        # 【红】README 第 2 条：移除之后 range_scan 不再输出该键。
        # 实际：第 0 层未摘除，range_scan 沿底层链仍能扫到被删节点。
        sl = SkipList(seed=1)
        sl.insert(3, "x")
        sl.remove(3)
        self.assertEqual(sl.range_scan(), [])

    def test_remove_twice_second_returns_false(self):
        # 【红】README 第 2 条：每个副本只存在一次，唯一副本被移除后
        # 再次 remove 应返回 False（没有副本可删）。
        # 实际：节点仍留在第 0 层，第二次 remove 依旧找到它并返回 True，
        # 且 len 被减成负数。
        sl = SkipList(seed=1)
        sl.insert(3, "x")
        self.assertTrue(sl.remove(3))
        self.assertFalse(sl.remove(3))

    def test_remove_oldest_copy_leaves_newer(self):
        # 【红】README 第 2、3 条：同键两个副本，remove 恰移除最旧的一个，
        # 之后 find 应返回较新副本的 value "b"。
        # 实际：副本根本没上链（见 test_duplicate_copies_coexist_in_insertion_order），
        # 且 remove 漏摘第 0 层，find 仍返回最旧的 "a"。
        sl = SkipList(seed=1)
        sl.insert(5, "a")
        sl.insert(5, "b")
        self.assertTrue(sl.remove(5))
        self.assertEqual(sl.find(5), "b")


class TestLen(unittest.TestCase):
    """README 第 4 条：len() 等于副本总数，与 range_scan 输出条数一致。"""

    def test_len_counts_distinct_inserts(self):
        sl = SkipList(seed=1)
        for k in range(50):
            sl.insert(k, str(k))
        self.assertEqual(len(sl), 50)

    def test_len_matches_range_scan_distinct(self):
        sl = SkipList(seed=2)
        for k in (9, 1, 7, 3, 4, 5):
            sl.insert(k)
        self.assertEqual(len(sl), len(sl.range_scan()))

    def test_len_counts_duplicate_copies(self):
        # 【红】README 第 1、4 条：同键插两次即有 2 个副本，len() 应为 2。
        # 实际：重复插入分支里 _size 多加了一次（+2 而非 +1），
        # 而副本又没真正上链，len() 变成 3。
        sl = SkipList(seed=1)
        sl.insert(5, "a")
        sl.insert(5, "b")
        self.assertEqual(len(sl), 2)

    def test_len_matches_range_scan_after_remove(self):
        # 【红】README 第 4 条：len() 与 range_scan() 输出条数一致。
        # 实际：remove 把 _size 减到 0，但节点仍留在第 0 层被扫出来，
        # len()==0 而 range_scan() 有 1 条。
        sl = SkipList(seed=1)
        sl.insert(3, "x")
        sl.remove(3)
        self.assertEqual(len(sl), len(sl.range_scan()))


class TestRangeScan(unittest.TestCase):
    """README 第 5 条：闭区间 [lo, hi]，非降序，None 无界，lo>hi 返回空。"""

    def setUp(self):
        self.sl = SkipList(seed=3)
        for k in (50, 20, 80, 10, 30, 70, 90, 60, 40):
            self.sl.insert(k, str(k))

    def test_full_scan_sorted(self):
        keys = [k for k, _ in self.sl.range_scan()]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(keys, [10, 20, 30, 40, 50, 60, 70, 80, 90])

    def test_closed_interval_inclusive_bounds(self):
        # 闭区间：lo、hi 本身若在表中必须包含。
        self.sl.insert(75, "75")
        keys = [k for k, _ in self.sl.range_scan(20, 80)]
        self.assertEqual(keys, [20, 30, 40, 50, 60, 70, 75, 80])

    def test_unbounded_sides(self):
        self.assertEqual([k for k, _ in self.sl.range_scan(hi=30)], [10, 20, 30])
        self.assertEqual([k for k, _ in self.sl.range_scan(lo=70)], [70, 80, 90])
        self.assertEqual(len(self.sl.range_scan(None, None)), 9)

    def test_lo_greater_than_hi_returns_empty(self):
        self.assertEqual(self.sl.range_scan(80, 20), [])

    def test_scan_outputs_key_value_tuples(self):
        for item in self.sl.range_scan():
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)


class TestMaxHeight(unittest.TestCase):
    """README 第 6 条：层级分布与 max_height 诊断属性。"""

    def test_empty_max_height_is_zero(self):
        self.assertEqual(SkipList(seed=1).max_height, 0)

    def test_max_height_never_exceeds_cap(self):
        sl = SkipList(seed=4)
        for k in range(2000):
            sl.insert(k)
        self.assertLessEqual(sl.max_height, 16)

    def test_max_height_typical_at_thousand_scale(self):
        # 【红】README 第 6 条：P(height >= k) = (1/4)^(k-1)，
        # 千级元素规模下 max_height 通常不低于 4 层
        # （正确分布下 2000 个节点够不到 4 层的概率约 (1-1/64)^2000 ≈ 1e-14，
        # 留足余量；固定 seed 使结果确定）。
        # 实际：_random_height 的循环条件写成 h > _MAX_LEVEL（应为 <），
        # 循环体永远不执行，所有节点都是 1 层，max_height 恒为 1，
        # 跳表退化成单链表——这正是查询越来越慢的根源（README 第 7 条）。
        sl = SkipList(seed=42)
        for k in range(2000):
            sl.insert(k)
        self.assertGreaterEqual(sl.max_height, 4)

    def test_seed_makes_levels_reproducible(self):
        # README 开头：构造时可传 seed 复现随机层级。
        # 可观测的层级信息只有 max_height，同 seed 两次构建必须一致。
        a = SkipList(seed=7)
        b = SkipList(seed=7)
        for k in range(500):
            a.insert(k)
            b.insert(k)
        self.assertEqual(a.max_height, b.max_height)


if __name__ == "__main__":
    unittest.main()
