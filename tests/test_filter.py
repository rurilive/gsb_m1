"""AND/OR 嵌套条件与等值条件下推的行为测试。"""

import unittest

from qmini import Engine, ParseError

USERS = [
    {"name": "alice", "age": 34, "city": "bj"},
    {"name": "bob", "age": 28, "city": "sh"},
    {"name": "carol", "age": 41, "city": "bj"},
    {"name": "dave", "age": 28, "city": "gz"},
    {"name": "erin", "age": 22, "city": "bj"},
]


def fresh_engine():
    e = Engine()
    e.register("users", [dict(r) for r in USERS])
    return e


class TestNestedConditions(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def names(self, sql):
        return [r["name"] for r in self.engine.execute(sql)]

    def test_and_binds_tighter_than_or(self):
        # 等价于 city = 'bj' OR (age = 28 AND name = 'bob')
        got = self.names("SELECT name FROM users WHERE city = 'bj' OR age = 28 AND name = 'bob'")
        self.assertEqual(got, ["alice", "bob", "carol", "erin"])

    def test_parens_override_precedence(self):
        got = self.names("SELECT name FROM users WHERE (city = 'bj' OR city = 'sh') AND age > 30")
        self.assertEqual(got, ["alice", "carol"])

    def test_deeply_nested_parens(self):
        got = self.names(
            "SELECT name FROM users WHERE ((city = 'bj' AND age > 30) OR name = 'dave') AND age != 99")
        self.assertEqual(got, ["alice", "carol", "dave"])

    def test_or_of_and_subtrees(self):
        got = self.names(
            "SELECT name FROM users WHERE city = 'bj' AND age < 30 OR city = 'sh' AND age = 28")
        self.assertEqual(got, ["bob", "erin"])

    def test_keywords_case_insensitive(self):
        got = self.names("SELECT name FROM users WHERE city = 'bj' aNd age > 30 oR name = 'dave'")
        self.assertEqual(got, ["alice", "carol", "dave"])

    def test_empty_parens_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE ()")

    def test_missing_close_paren_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE (age > 1")

    def test_dangling_operator_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE age > 1 AND")

    def test_missing_column_still_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM users WHERE age > 1 AND tel = 1")


class TestNestedExplain(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_or_child_parenthesized_inside_and(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE age > 20 AND (city = 'bj' OR city = 'sh')")
        self.assertIn("Filter[age > 20 AND (city = 'bj' OR city = 'sh')]", text)

    def test_and_child_not_parenthesized_inside_or(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND age > 30 OR name = 'dave'")
        self.assertIn("Filter[city = 'bj' AND age > 30 OR name = 'dave']", text)

    def test_same_level_chain_rendered_flat(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE age > 20 AND age < 40 AND city != 'gz'")
        self.assertIn("Filter[age > 20 AND age < 40 AND city != 'gz']", text)


class TestEqualityPushdown(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_equality_filter_sits_below_rest(self):
        text = self.engine.explain(
            "SELECT name FROM users WHERE age >= 28 AND city = 'bj' AND name != 'bob'")
        self.assertEqual(text, "\n".join([
            "Project[cols=name]",
            "  Filter[age >= 28 AND name != 'bob']",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ]))

    def test_nested_and_flattened_before_split(self):
        # 右嵌套 AND 摊平后参与拆分，各组保持原有相对顺序
        text = self.engine.explain(
            "SELECT * FROM users WHERE age >= 28 AND (city = 'bj' AND name != 'bob')")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[age >= 28 AND name != 'bob']",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ]))

    def test_multiple_equalities_share_one_filter(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND age > 20 AND name = 'alice'")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[age > 20]",
            "    Filter[city = 'bj' AND name = 'alice']",
            "      SeqScan[table=users]",
        ]))

    def test_only_equalities_stay_single_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE city = 'bj' AND age = 34")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[city = 'bj' AND age = 34]",
            "    SeqScan[table=users]",
        ]))

    def test_only_rest_stays_single_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE age > 20 AND name != 'bob'")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[age > 20 AND name != 'bob']",
            "    SeqScan[table=users]",
        ]))

    def test_lone_condition_not_split(self):
        text = self.engine.explain("SELECT * FROM users WHERE city = 'bj'")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[city = 'bj']",
            "    SeqScan[table=users]",
        ]))

    def test_and_inside_or_subtree_untouched(self):
        # OR 子树内的 AND 不参与下推，等值留在原处
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND (name = 'alice' AND age = 34 OR age < 25)")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[name = 'alice' AND age = 34 OR age < 25]",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ]))

    def test_pushdown_with_sort_and_limit(self):
        text = self.engine.explain(
            "SELECT name FROM users WHERE city = 'bj' AND age >= 28 ORDER BY age DESC LIMIT 2")
        self.assertEqual(text, "\n".join([
            "Limit[n=2]",
            "  Project[cols=name]",
            "    Sort[key=age DESC]",
            "      Filter[age >= 28]",
            "        Filter[city = 'bj']",
            "          SeqScan[table=users]",
        ]))

    def test_pushed_plan_executes_same_result(self):
        got = [r["name"] for r in self.engine.execute(
            "SELECT name FROM users WHERE age >= 28 AND city = 'bj' AND name != 'bob'")]
        self.assertEqual(got, ["alice", "carol"])

    def test_or_subtree_and_executes_in_place(self):
        got = [r["name"] for r in self.engine.execute(
            "SELECT name FROM users WHERE city = 'bj' AND (name = 'alice' AND age = 34 OR age < 25)")]
        self.assertEqual(got, ["alice", "erin"])


if __name__ == "__main__":
    unittest.main()
