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
        sql = ("SELECT name FROM users WHERE city = 'sh' OR city = 'bj' "
               "AND age > 30")
        self.assertEqual(self.names(sql), ["alice", "bob", "carol"])

    def test_parens_override_precedence(self):
        sql = ("SELECT name FROM users WHERE (city = 'sh' OR city = 'bj') "
               "AND age > 30")
        self.assertEqual(self.names(sql), ["alice", "carol"])

    def test_arbitrary_nesting(self):
        sql = ("SELECT name FROM users WHERE dept = 'core' AND "
               "(city = 'bj' AND (age < 30 OR age > 40) OR name = 'alice')")
        self.assertEqual(self.names(sql), ["alice", "carol", "erin"])

    def test_mixed_ops_in_tree(self):
        sql = ("SELECT name FROM users WHERE age != 28 AND "
               "(dept = 'edge' OR age <= 22)")
        self.assertEqual(self.names(sql), ["erin"])

    def test_extra_parens_are_transparent(self):
        sql = "SELECT name FROM users WHERE ((city = 'bj'))"
        self.assertEqual(self.names(sql), ["alice", "carol", "erin"])

    def test_dangling_and_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE age > 1 AND")

    def test_empty_parens_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE ()")

    def test_unclosed_paren_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE (age > 1")

    def test_and_or_are_reserved(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT and FROM users")

    def test_missing_column_in_tree_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute(
                "SELECT * FROM users WHERE age > 1 AND tel = 1")


class TestNestedExplain(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_explain_shows_nesting(self):
        text = self.engine.explain(
            "SELECT name FROM users WHERE dept = 'core' AND "
            "(city = 'bj' OR age < 30)")
        self.assertEqual(text, "\n".join([
            "Project[cols=name]",
            "  Filter[(city = 'bj' OR age < 30)]",
            "    Filter[dept = 'core']",
            "      SeqScan[table=users]",
        ]))

    def test_explain_or_at_top(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE age > 40 OR city = 'gz' AND age < 30")
        self.assertIn("Filter[(age > 40 OR (city = 'gz' AND age < 30))]",
                      text)


class TestEqualityPushdown(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_equalities_sit_below_rest(self):
        text = self.engine.explain(
            "SELECT name FROM users WHERE city = 'bj' AND age >= 30 "
            "AND dept = 'core'")
        self.assertEqual(text, "\n".join([
            "Project[cols=name]",
            "  Filter[age >= 30]",
            "    Filter[(city = 'bj' AND dept = 'core')]",
            "      SeqScan[table=users]",
        ]))

    def test_pushdown_keeps_execution_semantics(self):
        sql = ("SELECT name FROM users WHERE city = 'bj' AND age >= 30 "
               "AND dept = 'core'")
        self.assertEqual([r["name"] for r in self.engine.execute(sql)],
                         ["alice", "carol"])

    def test_only_equalities_single_filter(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND dept = 'core'")
        self.assertEqual(text.count("Filter["), 1)
        self.assertIn("Filter[(city = 'bj' AND dept = 'core')]", text)

    def test_only_rest_single_filter(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE age > 20 AND age < 40")
        self.assertEqual(text.count("Filter["), 1)
        self.assertIn("Filter[(age > 20 AND age < 40)]", text)

    def test_neq_stays_in_rest(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE dept = 'core' AND age != 41")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[age != 41]",
            "    Filter[dept = 'core']",
            "      SeqScan[table=users]",
        ]))

    def test_nested_and_flattened_before_split(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE (city = 'bj' AND dept = 'core') "
            "AND age < 40")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[age < 40]",
            "    Filter[(city = 'bj' AND dept = 'core')]",
            "      SeqScan[table=users]",
        ]))

    def test_and_inside_or_untouched(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE dept = 'core' AND "
            "(city = 'bj' AND age > 30 OR name = 'dave')")
        self.assertEqual(text, "\n".join([
            "Project[cols=*]",
            "  Filter[((city = 'bj' AND age > 30) OR name = 'dave')]",
            "    Filter[dept = 'core']",
            "      SeqScan[table=users]",
        ]))

    def test_or_at_top_no_pushdown(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' OR age > 40")
        self.assertEqual(text.count("Filter["), 1)
        self.assertIn("Filter[(city = 'bj' OR age > 40)]", text)

    def test_pushdown_result_order_preserved(self):
        sql = ("SELECT name FROM users WHERE dept = 'edge' AND age <= 28 "
               "ORDER BY age DESC")
        self.assertEqual([r["name"] for r in self.engine.execute(sql)],
                         ["bob", "dave"])


if __name__ == "__main__":
    unittest.main()
