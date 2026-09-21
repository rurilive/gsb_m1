"""渲染、快照、摘要与关键路径的基线测试。"""

import unittest

import fixtures

from spanweave import build, critical_path, render_tree, snapshot, summary
from spanweave.builder import Tree


class TestRender(unittest.TestCase):

    def test_render_shape(self):
        self.assertEqual(render_tree(build(fixtures.TRACE)[0]),
                         fixtures.RENDER)

    def test_snapshot_shape(self):
        self.assertEqual(snapshot(build(fixtures.TRACE)[0]),
                         fixtures.SNAPSHOT)

    def test_empty_tree_renders_empty_string(self):
        empty = Tree("tr-empty", [], [])
        self.assertEqual(render_tree(empty), "")
        self.assertEqual(snapshot(empty), "trace tr-empty")


class TestSummary(unittest.TestCase):

    def setUp(self):
        self.tree = build(fixtures.TRACE)[0]

    def test_counts(self):
        got = summary(self.tree)
        self.assertEqual(got["spans"], 4)
        self.assertEqual(got["roots"], 1)
        self.assertEqual(got["unresolved"], 0)
        self.assertEqual(got["max_depth"], 2)

    def test_total_duration(self):
        self.assertEqual(summary(self.tree)["total_ms"], 178)

    def test_empty_tree(self):
        got = summary(Tree("tr-empty", [], []))
        self.assertEqual(got["spans"], 0)
        self.assertEqual(got["roots"], 0)
        self.assertEqual(got["total_ms"], 0)
        self.assertEqual(got["max_depth"], 0)


class TestCriticalPath(unittest.TestCase):

    def test_picks_the_slowest_chain(self):
        self.assertEqual(critical_path(build(fixtures.TRACE)[0]),
                         ["root", "c2"])

    def test_single_span_tree(self):
        records = [fixtures.span_record("only", None, 0, 12, trace_id="tr-o")]
        self.assertEqual(critical_path(build(records)[0]), ["only"])

    def test_empty_tree(self):
        self.assertEqual(critical_path(Tree("tr-empty", [], [])), [])


if __name__ == "__main__":
    unittest.main()
