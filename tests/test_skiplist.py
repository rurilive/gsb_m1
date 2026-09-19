"""锁定 skiplist/README.md「语义约定」逐条行为的单元测试。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v

所有用例均通过固定 seed 或纯确定性构造保证可独立重复运行，
不依赖任何时序或真实随机性。统计性质的断言留足了余量。
"""

import unittest

from skiplist.skiplist import SkipList


class TestInsertSemantics(unittest.TestCase):
    """README 第 1 条：insert 恒新增副本，不覆盖；同键副本先插的在前。"""

    def test_unique_keys_sorted_on_scan(self):
        sl = SkipList(seed=1)
        for key in (88, 72, 95, 60, 81):
            sl.insert(key, "v%d" % key)
        self.assertEqual(
            [k for k, _ in sl.range_scan()],
            [60, 72, 81, 88, 95],
        )

    # 红用例（缺陷：_splice 在同键前驱处直接 continue，重复副本根本没挂上 0 层链）
    # README 期望：同键副本全部共存，按插入先后排列，先插的在前。
    # 实际发生：后插的同键副本被丢弃，range_scan 只剩第一个副本。
    def test_duplicate_copies_coexist_in_insertion_order(self):
        sl = SkipList(seed=7)
        sl.insert(5, "a")
        sl.insert(5, "b")
        sl.insert(5, "c")
        self.assertEqual(
            sl.range_scan(),
            [(5, "a"), (5, "b"), (5, "c")],
        )

    def test_insert_does_not_overwrite_other_keys(self):
        sl = SkipList(seed=2)
        sl.insert(1, "one")
        sl.insert(3, "three")
        sl.insert(2, "two")
        self.assertEqual(
            sl.range_scan(),
            [(1, "one"), (2, "two"), (3, "three")],
        )


class TestLenSemantics(unittest.TestCase):
    """README 第 4 条：len() 等于副本总数，与 range_scan() 输出条数一致。"""

    def test_len_counts_unique_keys(self):
        sl = SkipList(seed=3)
        for i in range(50):
            sl.insert(i, i)
        self.assertEqual(len(sl), 50)
        self.assertEqual(len(sl), len(sl.range_scan()))

    # 红用例（缺陷：insert 命中同键分支时 _size 多加了一次，每插一个重复副本 len 涨 2）
    # README 期望：len() 等于副本总数，3 个副本 len 应为 3。
    # 实际发生：插入 3 个同键副本后 len() 为 5。
    def test_len_counts_each_copy_once(self):
        sl = SkipList(seed=7)
        sl.insert(5, "a")
        sl.insert(5, "b")
        sl.insert(5, "c")
        self.assertEqual(len(sl), 3)

    # 红用例（缺陷：len 重复计数 + 重复副本未上链，两个方向同时破坏一致性）
    # README 期望：len() 与 range_scan() 的输出条数一致。
    # 实际发生：len() 为 5 而 range_scan() 只有 1 条输出。
    def test_len_consistent_with_range_scan_on_duplicates(self):
        sl = SkipList(seed=7)
        sl.insert(5, "a")
        sl.insert(5, "b")
        sl.insert(5, "c")
        self.assertEqual(len(sl), len(sl.range_scan()))


class TestFindAndContains(unittest.TestCase):
    """README 第 3 条：存在任一副本即命中；find 返回最旧副本的 value。"""

    def test_find_hit_and_miss(self):
        sl = SkipList(seed=4)
        sl.insert(81, "erin")
        self.assertEqual(sl.find(81), "erin")
        self.assertIsNone(sl.find(70))
        self.assertIn(81, sl)
        self.assertNotIn(70, sl)

    def test_find_empty_list(self):
        sl = SkipList(seed=4)
        self.assertIsNone(sl.find(1))
        self.assertNotIn(1, sl)

    def test_find_returns_oldest_copy_value(self):
        sl = SkipList(seed=8)
        sl.insert(5, "old")
        sl.insert(5, "new")
        self.assertEqual(sl.find(5), "old")

    # 红用例（缺陷：__contains__ 用 find() is not None 判断，value 为 None 的副本被漏判）
    # README 期望：存在任一副本即命中，insert(9) 后 9 in sl 必须为 True。
    # 实际发生：value 取默认 None 时，9 in sl 为 False。
    def test_contains_with_none_value(self):
        sl = SkipList(seed=9)
        sl.insert(9)
        self.assertIn(9, sl)


class TestRemoveSemantics(unittest.TestCase):
    """README 第 2 条：remove 恰移除最旧副本；无副本返回 False 且不改结构。"""

    # 红用例（缺陷：remove 只摘了 1 层及以上的指针，漏摘 0 层，节点仍挂在底层链上）
    # README 期望：remove 返回 True 后该键无副本，__contains__ 为 False，
    #              range_scan 不再输出它，len 归零。
    # 实际发生：remove 返回 True 且 len 归零，但节点仍在 0 层，
    #          range_scan 照样输出、key in sl 仍为 True——删掉的键又冒出来。
    def test_remove_existing_key(self):
        sl = SkipList(seed=11)
        sl.insert(5, "x")
        self.assertTrue(sl.remove(5))
        self.assertNotIn(5, sl)
        self.assertEqual(sl.range_scan(), [])
        self.assertEqual(len(sl), 0)

    # 红用例（缺陷：重复副本未上链 + remove 漏摘 0 层，两个缺陷叠加）
    # README 期望：两个副本中恰移除最旧的，剩下 (5, "new")，find 返回 "new"。
    # 实际发生：最旧副本原样留在链上，find 仍返回 "old"。
    def test_remove_deletes_oldest_copy_only(self):
        sl = SkipList(seed=12)
        sl.insert(5, "old")
        sl.insert(5, "new")
        self.assertTrue(sl.remove(5))
        self.assertEqual(sl.range_scan(), [(5, "new")])
        self.assertEqual(sl.find(5), "new")
        self.assertEqual(len(sl), 1)

    def test_remove_missing_key_returns_false_and_keeps_structure(self):
        sl = SkipList(seed=13)
        sl.insert(1, "a")
        sl.insert(3, "c")
        before = sl.range_scan()
        self.assertFalse(sl.remove(2))
        self.assertFalse(sl.remove(99))
        self.assertEqual(len(sl), 2)
        self.assertEqual(sl.range_scan(), before)

    def test_remove_on_empty_list(self):
        sl = SkipList(seed=13)
        self.assertFalse(sl.remove(1))
        self.assertEqual(len(sl), 0)


class TestRangeScanSemantics(unittest.TestCase):
    """README 第 5 条：闭区间 [lo, hi]，None 无界，lo > hi 返回空列表。"""

    def setUp(self):
        self.sl = SkipList(seed=21)
        for i in range(1, 11):
            self.sl.insert(i, "v%d" % i)

    def test_closed_interval_includes_both_ends(self):
        self.assertEqual(
            [k for k, _ in self.sl.range_scan(3, 6)],
            [3, 4, 5, 6],
        )

    def test_unbounded_sides(self):
        self.assertEqual([k for k, _ in self.sl.range_scan(None, 2)], [1, 2])
        self.assertEqual([k for k, _ in self.sl.range_scan(9, None)], [9, 10])
        self.assertEqual(len(self.sl.range_scan(None, None)), 10)
        self.assertEqual(len(self.sl.range_scan()), 10)

    def test_lo_greater_than_hi_returns_empty(self):
        self.assertEqual(self.sl.range_scan(9, 2), [])

    def test_out_of_range_bounds(self):
        self.assertEqual(self.sl.range_scan(100, 200), [])
        self.assertEqual(len(self.sl.range_scan(-100, -1)), 0)
        self.assertEqual(len(self.sl.range_scan(0, 100)), 10)

    def test_non_decreasing_output(self):
        keys = [k for k, _ in self.sl.range_scan()]
        self.assertEqual(keys, sorted(keys))


class TestLevelDistribution(unittest.TestCase):
    """README 第 6 条：P(height >= k) = (1/4)^(k-1)，上限 16 层；
    max_height 空表为 0，千级规模通常不低于 4 层。"""

    def test_max_height_empty_is_zero(self):
        self.assertEqual(SkipList(seed=31).max_height, 0)

    # 红用例（缺陷：_random_height 的循环条件写成 h > _MAX_LEVEL，
    #          恒为 False，所有节点高度恒为 1，跳表退化成普通链表）
    # README 期望：千级元素规模下 max_height 通常不低于 4 层
    #             （正确分布下 P(1000 个节点全低于 4 层) < 2e-7，且本用例固定 seed，
    #             结果完全确定，不靠运气）。
    # 实际发生：插入 1000 个元素后 max_height 为 1。
    def test_max_height_scales_with_elements(self):
        sl = SkipList(seed=42)
        for i in range(1000):
            sl.insert(i, i)
        self.assertGreaterEqual(sl.max_height, 4)

    # 红用例（缺陷同上：_random_height 循环条件写反，高度恒为 1）
    # README 期望：P(height >= 2) = 1/4，P(height >= 3) = 1/16，上限 16 层。
    #             20000 次采样下比例断言留了约 16 倍标准差的余量，
    #             且固定 seed 使结果完全确定。
    # 实际发生：20000 次采样全部返回 1，height >= 2 的比例为 0。
    def test_random_height_distribution(self):
        sl = SkipList(seed=2024)
        samples = [sl._random_height() for _ in range(20000)]
        self.assertTrue(all(1 <= h <= 16 for h in samples))
        ratio_ge_2 = sum(1 for h in samples if h >= 2) / len(samples)
        ratio_ge_3 = sum(1 for h in samples if h >= 3) / len(samples)
        self.assertTrue(
            0.20 <= ratio_ge_2 <= 0.30,
            "P(height>=2) 应约 1/4，实测 %.4f" % ratio_ge_2,
        )
        self.assertTrue(
            0.03 <= ratio_ge_3 <= 0.10,
            "P(height>=3) 应约 1/16，实测 %.4f" % ratio_ge_3,
        )

    def test_seed_reproducibility(self):
        sl_a = SkipList(seed=99)
        sl_b = SkipList(seed=99)
        draws_a = [sl_a._random_height() for _ in range(500)]
        draws_b = [sl_b._random_height() for _ in range(500)]
        self.assertEqual(draws_a, draws_b)


if __name__ == "__main__":
    unittest.main()
