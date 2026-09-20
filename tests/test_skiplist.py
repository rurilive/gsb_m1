"""skiplist 语义测试：以 skiplist 对应 README 的语义约定为唯一准绳。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v
    python3 tests/test_skiplist.py

所有用例确定性可重复：随机数据一律用固定 seed，统计断言留足余量，
性能阈值放宽到 CI 稳定。红用例上方注释标明「README 期望 / 实际发生」。
"""

import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skiplist.skiplist import SkipList

SEED = 20260920


class TestInsertSemantics(unittest.TestCase):
    """README 第 1 条：insert 恒新增副本，同键副本按插入先后共存，先插在前。"""

    def test_insert_distinct_keys_scan_sorted(self):
        sl = SkipList(seed=SEED)
        for key in (88, 72, 95, 60, 81):
            sl.insert(key, str(key))
        self.assertEqual(
            sl.range_scan(),
            [(60, "60"), (72, "72"), (81, "81"), (88, "88"), (95, "95")],
        )

    # README 期望：insert(5,'a'); insert(5,'b') 后两个副本共存且先插在前，
    # range_scan 输出 [(5,'a'),(5,'b')]。
    # 实际发生：重复键副本根本没有入链，range_scan 只有 [(5,'a')]，
    # 第二个副本丢失（_splice 遇同键前驱直接跳过该层）。
    def test_insert_duplicate_keys_coexist_in_insertion_order(self):
        sl = SkipList(seed=SEED)
        sl.insert(5, "a")
        sl.insert(5, "b")
        sl.insert(5, "c")
        self.assertEqual(sl.range_scan(), [(5, "a"), (5, "b"), (5, "c")])


class TestRemoveSemantics(unittest.TestCase):
    """README 第 2 条：remove 恰移除最旧副本；无副本返回 False 且不改结构。"""

    # README 期望：remove(1) 返回 True 后键 1 无任何副本，
    # __contains__ 为 False，range_scan 不再输出它。
    # 实际发生：remove 返回 True 且 len 减了，但节点仍挂在第 0 层链上，
    # 1 in sl 仍为 True，range_scan 仍输出 (1,'x')——删掉的键又冒出来。
    def test_remove_unlinks_key_completely(self):
        sl = SkipList(seed=SEED)
        sl.insert(1, "x")
        sl.insert(2, "y")
        self.assertTrue(sl.remove(1))
        self.assertNotIn(1, sl)
        self.assertEqual(sl.range_scan(), [(2, "y")])

    # README 期望：remove 返回 False 时不改动任何结构。
    # 实际发生：与 README 一致（本用例为绿，锁定既有正确行为）。
    def test_remove_missing_key_is_noop(self):
        sl = SkipList()
        sl.insert(1, "x")
        sl.insert(2, "y")
        before = sl.range_scan()
        self.assertFalse(sl.remove(99))
        self.assertEqual(len(sl), 2)
        self.assertEqual(sl.range_scan(), before)

    # README 期望：同键有多个副本时 remove 恰移除最旧的一个，
    # 其余副本原地保留、顺序不变。
    # 实际发生：副本入链即丢失（见 insert 用例），remove 又不摘第 0 层，
    # 结果是 'old' 赖在链上、'new' 从未出现，len 也对不上。
    def test_remove_deletes_oldest_copy_only(self):
        sl = SkipList(seed=SEED)
        sl.insert(7, "old")
        sl.insert(7, "new")
        self.assertTrue(sl.remove(7))
        self.assertEqual(sl.range_scan(), [(7, "new")])
        self.assertEqual(len(sl), 1)


class TestFindSemantics(unittest.TestCase):
    """README 第 3 条：find 命中任一副本，返回最旧副本的 value；无副本返回 None。"""

    def test_find_returns_oldest_copy_value(self):
        sl = SkipList(seed=SEED)
        sl.insert(5, "first")
        sl.insert(5, "second")
        self.assertEqual(sl.find(5), "first")

    def test_find_missing_returns_none(self):
        sl = SkipList(seed=SEED)
        sl.insert(5, "x")
        self.assertIsNone(sl.find(4))
        self.assertIsNone(sl.find(6))
        self.assertNotIn(4, sl)
        self.assertIn(5, sl)

    # README 期望：唯一副本被 remove 后 find 返回 None（无副本即不命中）。
    # 实际发生：remove 没摘第 0 层，find 仍返回已删键的 value。
    def test_find_returns_none_after_last_copy_removed(self):
        sl = SkipList(seed=SEED)
        sl.insert(5, "x")
        sl.remove(5)
        self.assertIsNone(sl.find(5))


class TestLenSemantics(unittest.TestCase):
    """README 第 4 条：len() 等于副本总数，与 range_scan() 输出条数一致。"""

    def test_len_counts_distinct_inserts(self):
        sl = SkipList(seed=SEED)
        for key in range(50):
            sl.insert(key, key)
        self.assertEqual(len(sl), 50)
        self.assertEqual(len(sl), len(sl.range_scan()))

    # README 期望：len 等于副本总数——3 个不同键加 2 个同键副本共 5 个副本，
    # len 应为 5 且与 range_scan 条数一致。
    # 实际发生：重复键 insert 分支里 _size 多加了一次（每次重复插入 +2），
    # 而副本又没入链，len 变成 7、range_scan 只有 3 条，两者都对不上。
    def test_len_counts_each_copy_exactly_once(self):
        sl = SkipList(seed=SEED)
        sl.insert(1, "a")
        sl.insert(2, "b")
        sl.insert(3, "c")
        sl.insert(3, "d")
        sl.insert(3, "e")
        self.assertEqual(len(sl), 5)
        self.assertEqual(len(sl), len(sl.range_scan()))

    # README 期望：remove 成功后 len 与 range_scan 条数保持一致。
    # 实际发生：remove 只减计数不摘第 0 层节点，len 变 4 而 scan 仍 5 条。
    def test_len_consistent_with_scan_after_remove(self):
        sl = SkipList(seed=SEED)
        for key in range(5):
            sl.insert(key, key)
        sl.remove(2)
        self.assertEqual(len(sl), len(sl.range_scan()))


class TestRangeScanSemantics(unittest.TestCase):
    """README 第 5 条：闭区间 [lo, hi]，非降序，None 无界，lo > hi 返回空。"""

    def setUp(self):
        self.sl = SkipList(seed=SEED)
        for key in (5, 1, 3, 2, 4):
            self.sl.insert(key, str(key))

    def test_closed_interval(self):
        self.assertEqual(
            self.sl.range_scan(2, 4), [(2, "2"), (3, "3"), (4, "4")]
        )

    def test_unbounded_sides(self):
        full = [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]
        self.assertEqual(self.sl.range_scan(), full)
        self.assertEqual(self.sl.range_scan(None, 2), full[:2])
        self.assertEqual(self.sl.range_scan(4, None), full[3:])

    def test_lo_greater_than_hi_returns_empty(self):
        self.assertEqual(self.sl.range_scan(4, 2), [])

    def test_output_non_decreasing(self):
        keys = [k for k, _ in self.sl.range_scan()]
        self.assertEqual(keys, sorted(keys))


class TestLevelDistribution(unittest.TestCase):
    """README 第 6 条：P(height >= k) = (1/4)^(k-1)，上限 16；max_height 空表为 0。"""

    def test_max_height_empty_is_zero(self):
        self.assertEqual(SkipList(seed=SEED).max_height, 0)

    # README 期望：千级元素规模下 max_height 通常不低于 4 层
    # （4096 个节点全不超过 3 层的概率约 (1-1/64)^4096 ~ e^-64，余量极大）。
    # 实际发生：_random_height 的循环条件写成 h > _MAX_LEVEL，永不升层，
    # 所有节点高度恒为 1，max_height 一直是 1。
    def test_max_height_grows_with_size(self):
        sl = SkipList(seed=SEED)
        for key in range(4096):
            sl.insert(key, key)
        self.assertGreaterEqual(sl.max_height, 4)

    # README 期望：每层以 1/4 概率再升一层，即约 25% 的节点高度 >= 2。
    # 用 4000 个独立 seed 的单节点表采样，断言比例落在 [0.15, 0.35]，
    # 相对期望 0.25 留了约 20 倍标准差的余量。
    # 实际发生：升层条件写反，所有节点高度恒 1，比例为 0。
    def test_quarter_of_nodes_reach_level_two(self):
        trials = 4000
        tall = 0
        for seed in range(trials):
            sl = SkipList(seed=seed)
            sl.insert(1, 1)
            if sl.max_height >= 2:
                tall += 1
        ratio = tall / trials
        self.assertGreater(ratio, 0.15)
        self.assertLess(ratio, 0.35)


class _ReferenceModel:
    """朴素参考实现：dict 存同键副本队列（先插在前），键排序后展开。"""

    def __init__(self):
        self._copies = {}

    def insert(self, key, value):
        self._copies.setdefault(key, []).append(value)

    def remove(self, key):
        if key not in self._copies:
            return False
        queue = self._copies[key]
        queue.pop(0)
        if not queue:
            del self._copies[key]
        return True

    def find(self, key):
        queue = self._copies.get(key)
        return queue[0] if queue else None

    def __len__(self):
        return sum(len(queue) for queue in self._copies.values())

    def range_scan(self, lo=None, hi=None):
        out = []
        for key in sorted(self._copies):
            if lo is not None and key < lo:
                continue
            if hi is not None and key > hi:
                continue
            for value in self._copies[key]:
                out.append((key, value))
        return out


class TestDifferentialAgainstReference(unittest.TestCase):
    """不变量对拍：任意操作序列后，scan 有序且与插入集合一致、
    删除过的键不再出现、len 与实际键数一致。"""

    def _assert_consistent(self, sl, model, step):
        scan = sl.range_scan()
        expected = model.range_scan()
        self.assertEqual(
            len(sl), len(model), "step %d: len 与参考实现不一致" % step
        )
        self.assertEqual(
            len(scan), len(expected), "step %d: scan 条数不一致" % step
        )
        for index, (got, want) in enumerate(zip(scan, expected)):
            self.assertEqual(
                got, want, "step %d: scan 第 %d 项不一致" % (step, index)
            )

    # README 期望：固定 seed 的随机操作流（插入/删除/查询/区间遍历混排，
    # 含重复键与不存在键）下，skiplist 的可观察行为与朴素参考实现完全一致。
    # 实际发生：重复键副本不入链且 _size 多加（len 虚高、scan 缺副本），
    # remove 不摘第 0 层（删过的键仍在 scan/find 中出现），对拍很快失败。
    def test_random_op_stream_matches_reference(self):
        rng = random.Random(SEED)
        sl = SkipList(seed=SEED)
        model = _ReferenceModel()
        key_space = 150
        for step in range(3000):
            roll = rng.random()
            key = rng.randrange(key_space)
            if roll < 0.50:
                value = rng.randrange(10 ** 6)
                sl.insert(key, value)
                model.insert(key, value)
            elif roll < 0.70:
                self.assertEqual(
                    sl.remove(key), model.remove(key),
                    "step %d: remove(%d) 返回值不一致" % (step, key),
                )
            elif roll < 0.85:
                self.assertEqual(
                    sl.find(key), model.find(key),
                    "step %d: find(%d) 不一致" % (step, key),
                )
                self.assertEqual(
                    key in sl, model.find(key) is not None,
                    "step %d: contains(%d) 不一致" % (step, key),
                )
            else:
                lo = rng.randrange(key_space) if rng.random() < 0.8 else None
                hi = rng.randrange(key_space) if rng.random() < 0.8 else None
                self.assertEqual(
                    sl.range_scan(lo, hi), model.range_scan(lo, hi),
                    "step %d: range_scan(%r, %r) 不一致" % (step, lo, hi),
                )
            self._assert_consistent(sl, model, step)


class TestPerformance(unittest.TestCase):
    """README 第 7 条：查找/插入应为 O(log n)，键数 10 倍增长时
    总耗时不允许出现明显的超线性拐点。"""

    def _workload(self, n, deadline=None):
        rng = random.Random(SEED)
        keys = [rng.randrange(n * 4) for _ in range(n)]
        sl = SkipList(seed=SEED)
        start = time.perf_counter()
        for index, key in enumerate(keys):
            sl.insert(key, key)
            if deadline and (index & 1023) == 1023:
                if time.perf_counter() - start > deadline:
                    return None
        for index, key in enumerate(keys):
            sl.find(key)
            if deadline and (index & 1023) == 1023:
                if time.perf_counter() - start > deadline:
                    return None
        return time.perf_counter() - start

    # README 期望：第 6 条的层级分布成立时，插入+查找为 O(log n)，
    # 键数从 1 万翻到 10 万（10 倍）总耗时只应约 12 倍（n log n），
    # 阈值放宽到 40 倍保证 CI 稳定；另设 60 秒兜底时限（正确实现
    # 通常在 1~2 秒内完成，余量 30 倍以上）。
    # 实际发生：升层条件写反导致跳表退化为单链表，每次操作 O(n)、
    # 总耗时 O(n^2)，10 万键 workload 需十分钟量级，触发兜底时限判红。
    def test_no_superlinear_scaling_from_10k_to_100k(self):
        deadline = 60.0
        small = self._workload(10_000)
        large = self._workload(100_000, deadline=deadline)
        self.assertIsNotNone(
            large,
            "10 万键 workload 超过 %.0f 秒兜底时限，存在超线性拐点" % deadline,
        )
        self.assertLess(
            large / small, 40.0,
            "键数 10 倍增长，耗时 %.1f 倍，超出放宽阈值" % (large / small),
        )


if __name__ == "__main__":
    unittest.main()
