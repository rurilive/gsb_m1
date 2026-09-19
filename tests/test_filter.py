"""AND/OR 嵌套条件与等值条件下推的行为测试。"""

import unittest

from qmini import Engine, ParseError

USERS = [
    {"name": "alice", "age": 34, "city": "bj", "dept": "core"},
    {"name": "bob", "age": 28, "city": "sh", "dept": "edge"},
    {"name": "carol", "age": 41, "city": "bj", "dept": "core"},
    {"name": "dave", "age": 28, "city": "gz", "dept": "edge"},
    {"name": "erin", "age": 22, "city": "bj", "dept": "core"},
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
        # 等价于 age = 28 OR (city = 'bj' AND age > 30)
        got = self.names("SELECT name FROM users WHERE age = 28 OR city = 'bj' AND age > 30")
        self.assertEqual(got, ["alice", "bob", "carol", "dave"])

    def test_parentheses_override_precedence(self):
        got = self.names("SELECT name FROM users WHERE (age = 28 OR city = 'bj') AND age > 30")
        self.assertEqual(got, ["alice", "carol"])

    def test_deeply_nested_parens(self):
        sql = ("SELECT name FROM users WHERE (city = 'bj' AND (age < 30 OR dept = 'core')) "
               "OR (city = 'gz' AND age = 28)")
        self.assertEqual(self.names(sql), ["alice", "carol", "dave", "erin"])

    def test_and_or_case_insensitive(self):
        got = self.names("SELECT name FROM users WHERE city = 'sh' oR city = 'gz' AnD age = 28")
        self.assertEqual(got, ["bob", "dave"])

    def test_unbalanced_paren_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE (age > 30 AND city = 'bj'")

    def test_missing_column_in_nested_condition_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM users WHERE age > 30 AND (tel = 1 OR city = 'bj')")


class TestEqualityPushdown(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_explain_pushes_equalities_below_rest(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND (age >= 30 OR dept = 'core')")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[(age >= 30 OR dept = 'core')]",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ]))

    def test_explain_rest_keeps_relative_order(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE age > 20 AND city = 'bj' AND name != 'erin'")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[(age > 20 AND name != 'erin')]",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ]))

    def test_all_equalities_stay_single_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE city = 'bj' AND dept = 'core'")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[(city = 'bj' AND dept = 'core')]",
            "    SeqScan[table=users]",
        ]))

    def test_no_equality_stays_single_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE age > 20 AND age < 40")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[(age > 20 AND age < 40)]",
            "    SeqScan[table=users]",
        ]))

    def test_or_top_level_not_split(self):
        # 顶层是 OR：不摊平、不拆分，OR 子树内的 AND 原样保留
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' OR dept = 'core' AND age > 30")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[(city = 'bj' OR (dept = 'core' AND age > 30))]",
            "    SeqScan[table=users]",
        ]))

    def test_and_inside_or_subtree_not_flattened(self):
        # 顶层 AND 里有 OR 子树：只拆顶层，OR 内的 AND 不动
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND (dept = 'core' AND age > 30 OR city = 'gz')")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[((dept = 'core' AND age > 30) OR city = 'gz')]",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ]))

    def test_pushdown_preserves_results(self):
        names = [r["name"] for r in self.engine.execute(
            "SELECT name FROM users WHERE city = 'bj' AND (age >= 30 OR dept = 'edge')")]
        self.assertEqual(names, ["alice", "carol"])

    def test_pushdown_missing_column_still_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM users WHERE tel = 1 AND age > 1")


if __name__ == "__main__":
    unittest.main()
