"""对拍测试：独立的参考实现 vs spanweave 的重建结果。

参考实现严格按 README 契约另写一份：按 trace_id 分组、parent_id 挂树、
缺父/成环入 unresolved、兄弟按 (start_ms, span_id) 排序、负耗时归零。
在乱序、分多批、缺父、重传、时钟回拨、成环、多根的输入下，两边的
树形、渲染、快照、汇总与关键路径必须完全一致。
"""

import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spanweave import build, critical_path, render_tree, snapshot, summary
from spanweave.store import SpanStore

import fixtures


def ref_duration(record):
    delta = record["end_ms"] - record["start_ms"]
    return delta if delta > 0 else 0


def ref_build(records):
    """按 trace_id 分组再挂树，返回 {trace_id: tree_dict}。

    重传留先到的；tree_dict = {"roots": [...], "unresolved": [...]}，
    节点是 {"span": record, "children": [...]}。
    """
    deduped = {}
    for record in records:
        if record["span_id"] not in deduped:
            deduped[record["span_id"]] = record

    by_trace = {}
    for record in deduped.values():
        by_trace.setdefault(record["trace_id"], []).append(record)

    trees = {}
    order_key = lambda item: (item["span"]["start_ms"],
                              item["span"]["span_id"])
    for trace_id, spans in by_trace.items():
        nodes = {span["span_id"]: {"span": span, "children": []}
                 for span in spans}
        roots = []
        for node in nodes.values():
            parent_id = node["span"].get("parent_id") or None
            if parent_id is None:
                roots.append(node)
            else:
                parent = nodes.get(parent_id)
                if parent is not None:
                    parent["children"].append(node)

        reachable = set()
        stack = list(roots)
        while stack:
            node = stack.pop()
            if id(node) in reachable:
                continue
            reachable.add(id(node))
            stack.extend(node["children"])

        for node in nodes.values():
            node["children"].sort(key=order_key)
        roots.sort(key=order_key)
        unresolved = [node for node in nodes.values()
                      if id(node) not in reachable]
        unresolved.sort(key=order_key)
        for node in unresolved:
            node["children"] = []
        trees[trace_id] = {"roots": roots, "unresolved": unresolved}
    return trees


def ref_walk(roots):
    stack = [(0, root) for root in reversed(roots)]
    while stack:
        depth, node = stack.pop()
        yield depth, node
        for child in reversed(node["children"]):
            stack.append((depth + 1, child))


def ref_render(tree):
    lines = []
    for depth, node in ref_walk(tree["roots"]):
        name = node["span"].get("name") or node["span"]["span_id"]
        lines.append("%s%s (%dms)" % ("  " * depth, name,
                                      ref_duration(node["span"])))
    return "\n".join(lines)


def ref_snapshot(tree, trace_id):
    lines = ["trace %s" % trace_id]
    for depth, node in ref_walk(tree["roots"]):
        span = node["span"]
        service = span.get("service") or "-"
        lines.append("%s%s %s %dms" % ("  " * depth, span["span_id"],
                                       service, ref_duration(span)))
    return "\n".join(lines)


def ref_summary(tree):
    spans = total_ms = max_depth = clock_skew = 0
    for depth, node in ref_walk(tree["roots"]):
        spans += 1
        total_ms += ref_duration(node["span"])
        max_depth = max(max_depth, depth)
        span = node["span"]
        if span["end_ms"] < span["start_ms"]:
            clock_skew += 1
    for node in tree["unresolved"]:
        span = node["span"]
        if span["end_ms"] < span["start_ms"]:
            clock_skew += 1
    return {
        "spans": spans,
        "roots": len(tree["roots"]),
        "unresolved": len(tree["unresolved"]),
        "clock_skew": clock_skew,
        "total_ms": total_ms,
        "max_depth": max_depth,
    }


def ref_critical_path(tree):
    roots = tree["roots"]
    if not roots:
        return []
    totals = {}
    paths = {}
    stack = [(root, False) for root in roots]
    while stack:
        node, processed = stack.pop()
        if processed:
            duration = ref_duration(node["span"])
            best_total = None
            best_ids = None
            for child in node["children"]:
                total = duration + totals[id(child)]
                ids = [node["span"]["span_id"]] + paths[id(child)]
                if best_total is None or total > best_total or (
                        total == best_total and ids < best_ids):
                    best_total, best_ids = total, ids
            if best_total is None:
                best_total = duration
                best_ids = [node["span"]["span_id"]]
            totals[id(node)] = best_total
            paths[id(node)] = best_ids
        elif id(node) not in totals:
            stack.append((node, True))
            for child in reversed(node["children"]):
                stack.append((child, False))
    best_total = None
    best_ids = None
    for root in roots:
        total, ids = totals[id(root)], paths[id(root)]
        if best_total is None or total > best_total or (
                total == best_total and ids < best_ids):
            best_total, best_ids = total, ids
    return best_ids


def ref_outputs(records):
    """参考实现的全部可比对输出，按 trace_id 排序装成列表。"""
    trees = ref_build(records)
    out = []
    for trace_id in sorted(trees):
        tree = trees[trace_id]
        out.append((
            trace_id,
            ref_render(tree),
            ref_snapshot(tree, trace_id),
            ref_summary(tree),
            tuple(ref_critical_path(tree)),
            tuple(node["span"]["span_id"] for node in tree["unresolved"]),
        ))
    return out


def weave_outputs(records):
    """spanweave 一侧与参考实现对齐的输出。"""
    out = []
    for tree in build(list(records)):
        out.append((
            tree.trace_id,
            render_tree(tree),
            snapshot(tree),
            summary(tree),
            tuple(critical_path(tree)),
            tuple(node.span.span_id for node in tree.unresolved),
        ))
    return out


def make_scenario(rng, n_spans=120, n_traces=3, missing_parent_rate=0.15,
                  skew_rate=0.1, same_tick_rate=0.3, cycle_rate=0.4):
    """造包含缺父、回拨、同毫秒、环、多根的一组记录。"""
    records = []
    next_id = 0
    for trace_index in range(n_traces):
        trace_id = "tr-%02d" % trace_index
        ids = []
        trace_records = []
        for _ in range(n_spans):
            span_id = "%s-s%05d" % (trace_id, next_id)
            next_id += 1
            ids.append(span_id)
            parent_id = None
            if len(ids) > 1 and rng.random() > 0.2:
                parent_id = rng.choice(ids[:-1])
            start_ms = rng.randrange(0, 500)
            if rng.random() < same_tick_rate and trace_records:
                start_ms = rng.choice(trace_records)["start_ms"]
            end_ms = start_ms + rng.randrange(0, 100)
            if rng.random() < skew_rate:
                end_ms = start_ms - rng.randrange(1, 50)
            record = {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": parent_id,
                "name": "op-%03d" % rng.randrange(20),
                "service": rng.choice(["api", "mysql", "redis", ""]),
                "start_ms": start_ms,
                "end_ms": end_ms,
            }
            records.append(record)
            trace_records.append(record)
        # 父始终不来：把一部分 span 的 parent 换成不存在的 id
        for record in rng.sample(
                trace_records,
                max(1, int(n_spans * missing_parent_rate))):
            record["parent_id"] = "ghost-%06d" % rng.randrange(1000000)
        # 互指成环：随机挑两条互相指向
        if n_spans >= 4 and rng.random() < cycle_rate:
            a, b = rng.sample(trace_records, 2)
            a["parent_id"], b["parent_id"] = b["span_id"], a["span_id"]
    return records


def store_outputs(store):
    out = []
    for tree in store.traces():
        out.append((
            tree.trace_id,
            render_tree(tree),
            snapshot(tree),
            summary(tree),
            tuple(critical_path(tree)),
            tuple(node.span.span_id for node in tree.unresolved),
        ))
    return out


class TestReferenceDifferential(unittest.TestCase):

    def assertMatchesReference(self, records):
        self.assertEqual(weave_outputs(records), ref_outputs(records))

    def test_fixture_trace(self):
        self.assertMatchesReference(fixtures.TRACE)

    def test_shuffled_order_is_byte_identical(self):
        rng = random.Random(20260921)
        for _ in range(20):
            records = make_scenario(rng)
            baseline = weave_outputs(records)
            for _ in range(5):
                shuffled = records[:]
                rng.shuffle(shuffled)
                self.assertEqual(weave_outputs(shuffled), baseline)

    def test_differential_random_scenarios(self):
        rng = random.Random(987654321)
        for seed in range(60):
            rng.seed(1000 + seed)
            self.assertMatchesReference(make_scenario(rng))

    def test_differential_retransmission(self):
        rng = random.Random(424242)
        for _ in range(10):
            records = make_scenario(rng, n_spans=60)
            bloated = records[:]
            for record in rng.sample(records, 20):
                bloated.insert(rng.randrange(len(bloated) + 1),
                               dict(record))
            rng.shuffle(bloated)
            self.assertMatchesReference(bloated)

    def test_differential_batched_feeds_match_one_shot(self):
        rng = random.Random(777)
        records = make_scenario(rng, n_spans=200)
        rng.shuffle(records)
        expected = weave_outputs(records)
        for chunk_size in (1, 3, 17, 64, 500):
            store = SpanStore()
            for index in range(0, len(records), chunk_size):
                store.feed(records[index:index + chunk_size])
            self.assertEqual(store_outputs(store), expected)

    def test_first_arrival_wins_on_retransmit(self):
        first = {
            "trace_id": "tr-1", "span_id": "s1", "parent_id": None,
            "name": "first", "service": "api", "start_ms": 0, "end_ms": 10,
        }
        retried = dict(first, name="second", end_ms=99)
        tree = build([first, retried])[0]
        self.assertEqual(tree.roots[0].span.name, "first")
        self.assertEqual(tree.roots[0].span.end_ms, 10)

    def test_missing_parent_goes_unresolved_and_is_not_lost(self):
        records = [
            {"trace_id": "tr-1", "span_id": "orphan", "parent_id": "ghost",
             "name": "orphan", "service": "w", "start_ms": 5, "end_ms": 9},
            {"trace_id": "tr-1", "span_id": "root", "parent_id": None,
             "name": "root", "service": "api", "start_ms": 0, "end_ms": 100},
        ]
        tree = build(records)[0]
        self.assertEqual([n.span.span_id for n in tree.roots], ["root"])
        self.assertEqual([n.span.span_id for n in tree.unresolved],
                         ["orphan"])
        self.assertEqual(summary(tree)["spans"], 1)
        self.assertEqual(summary(tree)["unresolved"], 1)

    def test_cycle_goes_unresolved(self):
        records = [
            {"trace_id": "tr-1", "span_id": "a", "parent_id": "b",
             "name": "a", "service": "", "start_ms": 0, "end_ms": 10},
            {"trace_id": "tr-1", "span_id": "b", "parent_id": "a",
             "name": "b", "service": "", "start_ms": 1, "end_ms": 9},
            {"trace_id": "tr-1", "span_id": "r", "parent_id": None,
             "name": "r", "service": "", "start_ms": 0, "end_ms": 20},
        ]
        tree = build(records)[0]
        self.assertEqual([n.span.span_id for n in tree.roots], ["r"])
        self.assertEqual([n.span.span_id for n in tree.unresolved],
                         ["a", "b"])
        self.assertMatchesReference(records)

    def test_self_loop_goes_unresolved(self):
        records = [
            {"trace_id": "tr-1", "span_id": "self", "parent_id": "self",
             "name": "self", "service": "", "start_ms": 0, "end_ms": 3},
        ]
        tree = build(records)[0]
        self.assertEqual(tree.roots, [])
        self.assertEqual([n.span.span_id for n in tree.unresolved], ["self"])

    def test_late_parent_gets_attached(self):
        store = SpanStore()
        store.feed([fixtures.span_record("c1", "root", 10, 20)])
        store.feed([fixtures.span_record("root", None, 0, 100,
                                         name="handle")])
        tree = store.traces()[0]
        self.assertEqual(len(tree.roots), 1)
        self.assertEqual(
            [c.span.span_id for c in tree.roots[0].children], ["c1"])
        self.assertEqual(tree.unresolved, [])

    def test_negative_duration_counts_as_zero_and_skew(self):
        records = [
            fixtures.span_record("root", None, 0, 100),
            fixtures.span_record("bad", "root", 80, 0),
        ]
        tree = build(records)[0]
        self.assertEqual(tree.roots[0].children[0].span.duration_ms, 0)
        self.assertEqual(summary(tree)["clock_skew"], 1)
        self.assertEqual(summary(tree)["total_ms"], 100)
        self.assertEqual(critical_path(tree), ["root", "bad"])

    def test_multiple_roots_from_cross_process_reports(self):
        records = [fixtures.TRACE[0], fixtures.TRACE[1], fixtures.TRACE[2], {
            "trace_id": "tr-1", "span_id": "loner",
            "name": "loner", "service": "worker",
            "start_ms": 120, "end_ms": 130,
        }]
        tree = build(records)[0]
        self.assertEqual(
            [n.span.span_id for n in tree.roots], ["root", "loner"])

    def test_critical_path_tie_picks_smallest_span_id_sequence(self):
        records = [
            fixtures.span_record("root", None, 0, 100),
            fixtures.span_record("z-child", "root", 10, 20),
            fixtures.span_record("a-child", "root", 10, 20),
        ]
        self.assertEqual(critical_path(build(records)[0]),
                         ["root", "a-child"])

    def test_deep_chain_thousands_of_levels(self):
        depth = 4000
        records = [fixtures.span_record(
            "d%05d" % i, None if i == 0 else "d%05d" % (i - 1),
            i, i + 1) for i in range(depth)]
        tree = build(records)[0]
        self.assertEqual(summary(tree)["max_depth"], depth - 1)
        path = critical_path(tree)
        self.assertEqual(len(path), depth)
        self.assertEqual(path[0], "d00000")
        text = render_tree(tree)
        self.assertEqual(text.count("\n"), depth - 1)
        self.assertTrue(text.endswith("  " * (depth - 1) + "d%05d (1ms)"
                                      % (depth - 1)))

    def test_large_trace_rebuilds_within_budget(self):
        n_spans = 100000
        records = []
        for i in range(n_spans):
            parent = None
            if i and i % 17 != 0:
                parent = "s%07d" % ((i - 1) % 5000)
            elif i == 0:
                parent = None
            start = i * 2
            end = start + 1
            if i % 997 == 0:
                end = start - 3
            records.append({
                "trace_id": "tr-big", "span_id": "s%07d" % i,
                "parent_id": parent, "name": "n", "service": "svc",
                "start_ms": start, "end_ms": end,
            })
        shuffled = records[:]
        random.Random(31337).shuffle(shuffled)
        started = time.perf_counter()
        store = SpanStore()
        store.feed(shuffled)
        tree = store.traces()[0]
        stats = summary(tree)
        path = critical_path(tree)
        elapsed = time.perf_counter() - started
        self.assertEqual(stats["spans"] + stats["unresolved"], n_spans)
        self.assertEqual(stats["clock_skew"],
                         sum(1 for r in records if r["end_ms"] < r["start_ms"]))
        self.assertTrue(path)
        self.assertLess(elapsed, 5.0, "重建+统计+关键路径耗时 %.2fs" % elapsed)

    def test_large_trace_order_independent(self):
        n_spans = 20000
        records = []
        for i in range(n_spans):
            records.append({
                "trace_id": "tr-big", "span_id": "s%07d" % i,
                "parent_id": None if i == 0 else "s%07d" % (i - 1),
                "name": "n", "service": "svc",
                "start_ms": i % 37, "end_ms": (i % 37) + 1,
            })
        one = snapshot(build(records)[0])
        shuffled = records[:]
        random.Random(2024).shuffle(shuffled)
        two = snapshot(build(shuffled)[0])
        self.assertEqual(one, two)


if __name__ == "__main__":
    unittest.main()
