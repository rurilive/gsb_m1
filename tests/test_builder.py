"""挂树结构的基线测试。

样例数据都是完整的（每个 parent_id 都能在本 trace 里找到），
时间戳互不相同。
"""

import unittest

import fixtures

from spanweave import build


def tree_of(records):
    return build(records)[0]


def shape(node):
    """把一棵子树摊成 (span_id, [子形状]) 的嵌套结构，方便比对。"""
    return (node.span.span_id, [shape(child) for child in node.children])


class TestBuildTree(unittest.TestCase):

    def test_hierarchy_matches_parent_ids(self):
        tree = tree_of(fixtures.TRACE)
        self.assertEqual(shape(tree.roots[0]),
                         ("root", [("c1", [("g1", [])]), ("c2", [])]))

    def test_single_root(self):
        tree = tree_of(fixtures.TRACE)
        self.assertEqual(len(tree.roots), 1)
        self.assertEqual(tree.roots[0].span.span_id, "root")

    def test_every_span_is_in_the_tree(self):
        tree = tree_of(fixtures.TRACE)
        seen = []

        def walk(node):
            seen.append(node.span.span_id)
            for child in node.children:
                walk(child)

        for root in tree.roots:
            walk(root)
        self.assertEqual(sorted(seen), ["c1", "c2", "g1", "root"])

    def test_nothing_is_unresolved(self):
        tree = tree_of(fixtures.TRACE)
        self.assertEqual(tree.unresolved, [])

    def test_sibling_order_ignores_arrival_order(self):
        # root 先喂，两个子 span 反过来喂：c2 先到，c1 后到
        samples = [fixtures.TRACE[index] for index in (0, 3, 1, 2)]
        tree = tree_of(samples)
        self.assertEqual(shape(tree.roots[0]),
                         ("root", [("c1", [("g1", [])]), ("c2", [])]))
        starts = [child.span.start_ms for child in tree.roots[0].children]
        self.assertEqual(starts, sorted(starts))

    def test_empty_parent_id_is_a_root(self):
        records = [
            fixtures.span_record("x1", "", 0, 10, trace_id="tr-x"),
            fixtures.span_record("x2", "x1", 20, 30, trace_id="tr-x"),
        ]
        tree = tree_of(records)
        self.assertEqual(len(tree.roots), 1)
        self.assertEqual(tree.roots[0].span.span_id, "x1")
        self.assertEqual(len(tree.roots[0].children), 1)

    def test_traces_are_independent(self):
        records = fixtures.TRACE + [
            fixtures.span_record("y1", None, 0, 7, trace_id="tr-y"),
        ]
        trees = build(records)
        self.assertEqual([tree.trace_id for tree in trees], ["tr-1", "tr-y"])
        self.assertEqual(len(trees[0].roots[0].children), 2)
        self.assertEqual(len(trees[1].roots), 1)


if __name__ == "__main__":
    unittest.main()
