"""SpanStore 收数行为的基线测试。

样例数据都按父在前、子在后、时间戳互不相同的顺序喂进去。
"""

import unittest

import fixtures

from spanweave import build
from spanweave.store import SpanStore


class TestSpanStore(unittest.TestCase):

    def test_parent_first_batch_is_ingested(self):
        store = SpanStore()
        store.feed(fixtures.TRACE)
        trees = store.traces()
        self.assertEqual(len(trees), 1)
        self.assertEqual(trees[0].trace_id, "tr-1")
        self.assertEqual(len(trees[0].roots), 1)
        self.assertEqual(trees[0].roots[0].span.span_id, "root")
        self.assertEqual(len(trees[0].roots[0].children), 2)

    def test_retransmitted_span_is_kept_once(self):
        store = SpanStore()
        store.feed(fixtures.TRACE)
        store.feed(fixtures.TRACE)
        tree = store.traces()[0]
        self.assertEqual(len(tree.roots[0].children), 2)
        self.assertEqual(store.traces()[0].roots[0].span.name, "handle")

    def test_traces_are_sorted_by_trace_id(self):
        store = SpanStore()
        store.feed([
            fixtures.span_record("b1", None, 0, 30, trace_id="tr-b"),
            fixtures.span_record("b2", "b1", 10, 20, trace_id="tr-b"),
            fixtures.span_record("a1", None, 0, 5, trace_id="tr-a"),
        ])
        self.assertEqual([tree.trace_id for tree in store.traces()],
                         ["tr-a", "tr-b"])

    def test_batches_are_equivalent_to_one_feed(self):
        split = SpanStore()
        split.feed(fixtures.TRACE[:1])
        split.feed(fixtures.TRACE[1:])
        one_shot = SpanStore()
        one_shot.feed(list(fixtures.TRACE))
        self.assertEqual(len(split.traces()), len(one_shot.traces()))
        self.assertEqual(split.traces()[0].roots[0].span.span_id,
                         one_shot.traces()[0].roots[0].span.span_id)

    def test_build_is_a_shortcut(self):
        tree = build(fixtures.TRACE)[0]
        self.assertEqual(tree.trace_id, "tr-1")
        self.assertEqual(tree.roots[0].span.span_id, "root")

    def test_feed_accepts_a_generator(self):
        store = SpanStore()
        store.feed(record for record in fixtures.TRACE)
        self.assertEqual(len(store.traces()), 1)


if __name__ == "__main__":
    unittest.main()
