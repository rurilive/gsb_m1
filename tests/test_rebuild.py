"""重建正确性的对拍与性能测试。

参考实现 reference_build 故意写得笨而直白：按 trace_id 分组、去重后
直接按 parent_id 挂树，再从根出发收敛出树上与 unresolved 的集合。
主实现（SpanStore + builder）在乱序、缺父、重传、时钟回拨的输入下，
树形、unresolved、渲染、快照、汇总、关键路径必须与参考实现完全一致。
"""

import random
import time
import unittest

from spanweave import SpanStore, build, critical_path, render_tree, snapshot
from spanweave import summary
from spanweave.builder import Node, Tree
from spanweave.model import Span


# ---------------------------------------------------------------- 参考实现

def reference_build(records):
    """按 trace_id 分组再挂树的参考实现，返回 Tree 列表。"""
    seen = {}
    for record in records:
        span = Span.from_record(record)
        if span.span_id not in seen:
            seen[span.span_id] = span
    by_trace = {}
    for span in seen.values():
        by_trace.setdefault(span.trace_id, []).append(span)
    return [reference_tree(trace_id, by_trace[trace_id])
            for trace_id in sorted(by_trace)]


def reference_tree(trace_id, spans):
    by_id = {}
    for span in spans:
        by_id[span.span_id] = Node(span)

    def reaches_root(span):
        """沿 parent 链向上走，能走到无父的 span 才算在树上。"""
        walked = set()
        current = span
        while current.parent_id is not None:
            if current.parent_id in walked or current.parent_id not in by_id:
                return False
            walked.add(current.parent_id)
            current = by_id[current.parent_id].span
        return True

    on_tree = {span.span_id for span in spans if reaches_root(span)}
    key = lambda span: (span.start_ms, span.span_id)
    roots = []
    for span in sorted(spans, key=key):
        if span.span_id not in on_tree:
            continue
        node = by_id[span.span_id]
        if span.parent_id is None:
            roots.append(node)
        else:
            by_id[span.parent_id].children.append(node)
    unresolved = [by_id[span.span_id]
                  for span in sorted(spans, key=key)
                  if span.span_id not in on_tree]
    return Tree(trace_id, roots, unresolved)


# ---------------------------------------------------------------- 比对工具

def shape_of(node):
    """摊成 (span_id, 耗时, [子形状])，递归仅用于对拍里的小树。"""
    return (node.span.span_id, node.span.duration_ms,
            tuple(shape_of(child) for child in node.children))


def tree_blob(tree):
    """一棵树所有对外输出的拼接，逐字节比对用。"""
    return "\n".join([
        render_tree(tree),
        snapshot(tree),
        repr(sorted(summary(tree).items())),
        repr(critical_path(tree)),
        repr([node.span.span_id for node in tree.unresolved]),
    ])


def assert_same_trees(test_case, expected, actual):
    test_case.assertEqual([tree.trace_id for tree in expected],
                          [tree.trace_id for tree in actual])
    for want, got in zip(expected, actual):
        test_case.assertEqual([shape_of(root) for root in want.roots],
                              [shape_of(root) for root in got.roots])
        test_case.assertEqual(tree_blob(want), tree_blob(got))


# ---------------------------------------------------------------- 随机数据

def random_records(rng):
    """生成一批带乱序、缺父、自指、成环、重传、时钟回拨的记录。"""
    records = []
    for trace_no in range(rng.randint(1, 3)):
        trace_id = "tr-%d" % trace_no
        count = rng.randint(1, 30)
        ids = ["s%d-%d" % (trace_no, index) for index in range(count)]
        for index, span_id in enumerate(ids):
            dice = rng.random()
            if index == 0 or dice < 0.15:
                parent_id = None
            elif dice < 0.30:
                parent_id = rng.choice(ids)        # 可能自指或成环
            elif dice < 0.38:
                parent_id = "gone-%d" % rng.randint(0, 2)  # 父始终不来
            else:
                parent_id = ids[rng.randrange(index)]
            start_ms = rng.randint(0, 60)
            end_ms = start_ms + rng.randint(-8, 40)  # 负的即时钟回拨
            records.append({
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": parent_id,
                "name": "n-%s" % span_id,
                "service": rng.choice(["api", "db", ""]),
                "start_ms": start_ms,
                "end_ms": end_ms,
            })
    for record in list(records):
        if rng.random() < 0.15:
            records.append(dict(record))           # 重传，内容不变
    rng.shuffle(records)
    return records


def feed_in_random_batches(records, rng):
    store = SpanStore()
    pending = list(records)
    while pending:
        cut = rng.randint(1, len(pending))
        store.feed(pending[:cut])
        pending = pending[cut:]
    return store.traces()


# ---------------------------------------------------------------- 测试

class TestDifferential(unittest.TestCase):

    def test_matches_reference_under_messy_inputs(self):
        for seed in range(200):
            rng = random.Random(seed)
            records = random_records(rng)
            with self.subTest(seed=seed):
                expected = reference_build(records)
                assert_same_trees(self, expected, build(records))
                assert_same_trees(self, expected,
                                  feed_in_random_batches(records, rng))

    def test_feed_order_is_irrelevant(self):
        rng = random.Random(99)
        records = random_records(rng)
        baseline = [tree_blob(tree) for tree in build(records)]
        for seed in range(30):
            shuffled = list(records)
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(baseline,
                             [tree_blob(tree) for tree in build(shuffled)])


class TestRebuildRules(unittest.TestCase):

    def test_late_parent_is_attached_when_it_arrives(self):
        store = SpanStore()
        store.feed([{"trace_id": "t", "span_id": "kid", "parent_id": "dad",
                     "name": "kid", "service": "s",
                     "start_ms": 5, "end_ms": 8}])
        self.assertEqual(store.traces()[0].unresolved[0].span.span_id, "kid")
        store.feed([{"trace_id": "t", "span_id": "dad", "parent_id": None,
                     "name": "dad", "service": "s",
                     "start_ms": 0, "end_ms": 10}])
        tree = store.traces()[0]
        self.assertEqual(tree.unresolved, [])
        self.assertEqual([node.span.span_id for node in tree.roots], ["dad"])
        self.assertEqual([node.span.span_id
                          for node in tree.roots[0].children], ["kid"])

    def test_missing_parent_is_unresolved_not_dropped(self):
        records = [
            {"trace_id": "t", "span_id": "root", "parent_id": None,
             "name": "r", "service": "s", "start_ms": 0, "end_ms": 9},
            {"trace_id": "t", "span_id": "orphan", "parent_id": "ghost",
             "name": "o", "service": "s", "start_ms": 1, "end_ms": 2},
        ]
        tree = build(records)[0]
        self.assertEqual([node.span.span_id for node in tree.unresolved],
                         ["orphan"])
        self.assertEqual(summary(tree)["unresolved"], 1)

    def test_cycles_and_self_loops_stay_out_of_the_tree(self):
        records = [
            {"trace_id": "t", "span_id": "root", "parent_id": None,
             "name": "r", "service": "s", "start_ms": 0, "end_ms": 9},
            {"trace_id": "t", "span_id": "self", "parent_id": "self",
             "name": "s", "service": "s", "start_ms": 1, "end_ms": 2},
            {"trace_id": "t", "span_id": "loop-a", "parent_id": "loop-b",
             "name": "a", "service": "s", "start_ms": 2, "end_ms": 3},
            {"trace_id": "t", "span_id": "loop-b", "parent_id": "loop-a",
             "name": "b", "service": "s", "start_ms": 3, "end_ms": 4},
            {"trace_id": "t", "span_id": "loop-kid", "parent_id": "loop-a",
             "name": "k", "service": "s", "start_ms": 4, "end_ms": 5},
        ]
        tree = build(records)[0]
        self.assertEqual([node.span.span_id for node in tree.roots], ["root"])
        self.assertEqual([node.span.span_id for node in tree.unresolved],
                         ["self", "loop-a", "loop-b", "loop-kid"])
        self.assertEqual(summary(tree)["unresolved"], 4)

    def test_clock_skew_counts_and_clamps_to_zero(self):
        records = [
            {"trace_id": "t", "span_id": "root", "parent_id": None,
             "name": "r", "service": "s", "start_ms": 0, "end_ms": 100},
            {"trace_id": "t", "span_id": "skew", "parent_id": "root",
             "name": "skew", "service": "s", "start_ms": 80, "end_ms": 10},
        ]
        tree = build(records)[0]
        got = summary(tree)
        self.assertEqual(got["clock_skew"], 1)
        self.assertEqual(got["total_ms"], 100)
        self.assertIn("skew (0ms)", render_tree(tree))

    def test_critical_path_tie_picks_lexicographically_smallest(self):
        records = [
            {"trace_id": "t", "span_id": "root", "parent_id": None,
             "name": "r", "service": "s", "start_ms": 0, "end_ms": 10},
            {"trace_id": "t", "span_id": "zb", "parent_id": "root",
             "name": "zb", "service": "s", "start_ms": 1, "end_ms": 6},
            {"trace_id": "t", "span_id": "aa", "parent_id": "root",
             "name": "aa", "service": "s", "start_ms": 2, "end_ms": 7},
        ]
        self.assertEqual(critical_path(build(records)[0]), ["root", "aa"])

    def test_deep_chain_renders_and_summarizes(self):
        depth = 5000
        records = []
        for index in range(depth):
            records.append({
                "trace_id": "t", "span_id": "d%05d" % index,
                "parent_id": "d%05d" % (index - 1) if index else None,
                "name": "n", "service": "s",
                "start_ms": index, "end_ms": index + 1,
            })
        tree = build(records)[0]
        got = summary(tree)
        self.assertEqual(got["spans"], depth)
        self.assertEqual(got["max_depth"], depth - 1)
        self.assertEqual(len(render_tree(tree).splitlines()), depth)
        self.assertEqual(len(critical_path(tree)), depth)


class TestPerformance(unittest.TestCase):

    def test_hundred_thousand_spans_within_five_seconds(self):
        rng = random.Random(7)
        count = 100000
        records = []
        for index in range(count):
            records.append({
                "trace_id": "big",
                "span_id": "sp%d" % index,
                "parent_id": ("sp%d" % rng.randrange(index))
                             if index else None,
                "name": "n%d" % index,
                "service": "svc",
                "start_ms": rng.randint(0, 10 ** 6),
                "end_ms": rng.randint(0, 10 ** 6),
            })
        rng.shuffle(records)
        started = time.perf_counter()
        store = SpanStore()
        store.feed(records)
        tree = store.traces()[0]
        got = summary(tree)
        critical_path(tree)
        snapshot(tree)
        elapsed = time.perf_counter() - started
        self.assertEqual(got["spans"] + got["unresolved"], count)
        self.assertLess(elapsed, 5.0,
                        "十万条 span 重建耗时 %.2fs，超过 5s" % elapsed)


if __name__ == "__main__":
    unittest.main()
