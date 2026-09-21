"""布尔查询与参考引擎的行为基线。"""

import unittest

from bitag.query import And, Diff, Not, Or, SetEngine, Tag, evaluate, parse
from bitag.store import TagStore


def build_store():
    store = TagStore()
    store.add(1, [3, 7])
    store.add(2, [7, 9])
    store.add(3, [3])
    store.add(4, [9, 11])
    store.add(5, [])
    return store


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.store = build_store()
        self.engine = SetEngine(self.store)

    def run_query(self, node):
        return evaluate(node, self.engine)

    def test_tag(self):
        self.assertEqual(self.run_query(Tag(3)), [1, 3])
        self.assertEqual(self.run_query(Tag(11)), [4])

    def test_unknown_label_matches_nothing(self):
        self.assertEqual(self.run_query(Tag(404)), [])

    def test_and_or(self):
        self.assertEqual(self.run_query(And(Tag(3), Tag(7))), [1])
        self.assertEqual(self.run_query(Or(Tag(3), Tag(9))), [1, 2, 3, 4])
        self.assertEqual(self.run_query(And(Tag(3), Tag(9), Tag(7))), [])

    def test_not_spans_every_record_including_labelless(self):
        self.assertEqual(self.run_query(Not(Tag(7))), [3, 4, 5])

    def test_diff(self):
        self.assertEqual(self.run_query(Diff(Tag(7), Tag(3))), [2])
        self.assertEqual(self.run_query(Diff(Not(Tag(7)), Tag(11))), [3, 5])

    def test_nested_expression(self):
        node = And(Or(Tag(3), Tag(9)), Not(Tag(7)))
        self.assertEqual(self.run_query(node), [3, 4])

    def test_results_are_sorted_lists(self):
        result = self.run_query(Not(Tag(404)))
        self.assertIsInstance(result, list)
        self.assertEqual(result, sorted(result))

    def test_evaluation_leaves_store_untouched(self):
        before = self.store.stats()
        self.run_query(Or(Tag(3), Tag(9)))
        self.run_query(Not(Tag(404)))
        self.assertEqual(self.store.stats(), before)
        self.assertEqual(self.store.postings(3), {1, 3})

    def test_repeated_evaluation_is_stable(self):
        node = And(Or(Tag(3), Tag(9)), Not(Tag(7)))
        first = self.run_query(node)
        self.run_query(Tag(3))
        self.assertEqual(self.run_query(node), first)

    def test_engine_counter_shape(self):
        self.run_query(Tag(3))
        stats = self.engine.stats()
        self.assertEqual(stats["engine"], "set")
        self.assertIsInstance(stats["ops"], int)
        self.assertIsInstance(stats["queries"], int)
        self.assertGreaterEqual(stats["queries"], 1)


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.store = build_store()
        self.engine = SetEngine(self.store)

    def test_parse_builds_nodes(self):
        self.assertEqual(parse("3"), Tag(3))
        self.assertEqual(parse("3&7"), And(Tag(3), Tag(7)))
        self.assertEqual(parse("3|7"), Or(Tag(3), Tag(7)))
        self.assertEqual(parse("~3"), Not(Tag(3)))
        self.assertEqual(parse("7-3"), Diff(Tag(7), Tag(3)))

    def test_parse_precedence(self):
        self.assertEqual(parse("1|2&3"), Or(Tag(1), And(Tag(2), Tag(3))))
        self.assertEqual(parse("~1&2"), And(Not(Tag(1)), Tag(2)))
        self.assertEqual(parse("(1|2)&3"), And(Or(Tag(1), Tag(2)), Tag(3)))

    def test_parse_and_evaluate_agree_with_tree(self):
        text = "3&(7|~9)"
        self.assertEqual(
            evaluate(parse(text), self.engine),
            evaluate(And(Tag(3), Or(Tag(7), Not(Tag(9)))), self.engine),
        )

    def test_parse_rejects_bad_input(self):
        for text in ("", "3 &", "3 & & 7", "(3", "3)", "3 $ 7", "&3"):
            with self.assertRaises(ValueError):
                parse(text)


if __name__ == "__main__":
    unittest.main()
