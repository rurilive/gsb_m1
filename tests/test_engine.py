"""qmini 现有行为的锁定测试。"""

import unittest

from qmini import Engine, ParseError
from qmini.plan import Compare, FilterNode, LimitNode, SeqScan

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


class TestParse(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_keywords_case_insensitive(self):
        rows = self.engine.execute("select name from users where city = 'bj' limit 1")
        self.assertEqual(rows, [{"name": "alice"}])

    def test_identifiers_case_sensitive(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT NAME FROM users")

    def test_missing_from(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT name users")

    def test_bad_operator(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE age == 30")

    def test_literal_must_be_on_right(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE 30 > age")

    def test_unterminated_string(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE city = 'bj")

    def test_trailing_tokens(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users WHERE age > 1 LIMIT 2 3")

    def test_negative_limit_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users LIMIT -1")

    def test_float_limit_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users LIMIT 2.5")

    def test_reserved_word_as_column_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT order FROM users")

    def test_semicolon_rejected(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT * FROM users;")


class TestExecute(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def names(self, sql):
        return [r["name"] for r in self.engine.execute(sql)]

    def test_select_star_keeps_row_order(self):
        rows = self.engine.execute("SELECT * FROM users")
        self.assertEqual([r["name"] for r in rows], ["alice", "bob", "carol", "dave", "erin"])
        self.assertEqual(rows[0], {"name": "alice", "age": 34, "city": "bj"})

    def test_projection_subsets_columns(self):
        rows = self.engine.execute("SELECT city, name FROM users LIMIT 1")
        self.assertEqual(rows, [{"city": "bj", "name": "alice"}])

    def test_compare_ops(self):
        cases = [
            ("age = 28", ["bob", "dave"]),
            ("age != 28", ["alice", "carol", "erin"]),
            ("age > 28", ["alice", "carol"]),
            ("age >= 28", ["alice", "bob", "carol", "dave"]),
            ("age < 28", ["erin"]),
            ("age <= 28", ["bob", "dave", "erin"]),
        ]
        for cond, expected in cases:
            self.assertEqual(self.names("SELECT name FROM users WHERE " + cond), expected, cond)

    def test_negative_and_float_literals(self):
        self.assertEqual(self.names("SELECT name FROM users WHERE age > 27.5 ORDER BY age"),
                         ["bob", "dave", "alice", "carol"])

    def test_order_by_default_asc_and_stable(self):
        # bob/dave 同为 28，保持注册先后
        self.assertEqual(self.names("SELECT name FROM users ORDER BY age"),
                         ["erin", "bob", "dave", "alice", "carol"])

    def test_order_by_desc_also_stable(self):
        self.assertEqual(self.names("SELECT name FROM users ORDER BY age DESC"),
                         ["carol", "alice", "bob", "dave", "erin"])

    def test_order_by_column_not_projected(self):
        rows = self.engine.execute("SELECT name FROM users ORDER BY age DESC LIMIT 1")
        self.assertEqual(rows, [{"name": "carol"}])

    def test_limit_zero(self):
        self.assertEqual(self.engine.execute("SELECT * FROM users LIMIT 0"), [])

    def test_limit_exceeds_row_count(self):
        self.assertEqual(len(self.engine.execute("SELECT * FROM users LIMIT 99")), 5)

    def test_result_rows_are_copies(self):
        rows = self.engine.execute("SELECT * FROM users")
        rows[0]["name"] = "hacked"
        again = self.engine.execute("SELECT * FROM users")
        self.assertEqual(again[0]["name"], "alice")

    def test_no_match_returns_empty(self):
        self.assertEqual(self.engine.execute("SELECT * FROM users WHERE age > 100"), [])

    def test_unknown_table_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM nope")

    def test_unknown_column_in_projection_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT tel FROM users")

    def test_unknown_column_in_where_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM users WHERE tel = 1")

    def test_register_rejects_non_list(self):
        with self.assertRaises(TypeError):
            Engine().register("t", {"a": 1})


class TestPlanIterators(unittest.TestCase):
    def test_seqscan_and_filter_directly(self):
        scan = SeqScan("users", USERS)
        cond = Compare(">", "age", 28)
        got = [r["name"] for r in FilterNode(scan, cond)]
        self.assertEqual(got, ["alice", "carol"])

    def test_limit_pulls_lazily(self):
        pulled = []

        def source():
            for r in USERS:
                pulled.append(r["name"])
                yield r

        scan = SeqScan("users", source())
        got = [r["name"] for r in LimitNode(scan, 2)]
        self.assertEqual(got, ["alice", "bob"])
        self.assertEqual(pulled, ["alice", "bob"])  # 第 3 行没有被拉取


class TestExplain(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_explain_canonical(self):
        text = self.engine.explain(
            "SELECT name, age FROM users WHERE age >= 30 ORDER BY age DESC LIMIT 2")
        self.assertEqual(text, "\n".join([
            "Limit[n=2]",
            "  Project[cols=name, age]",
            "    Sort[key=age DESC]",
            "      Filter[age >= 30]",
            "        SeqScan[table=users]",
        ]))

    def test_explain_asc_default(self):
        text = self.engine.explain("SELECT * FROM users ORDER BY age")
        self.assertIn("Sort[key=age ASC]", text)

    def test_explain_string_condition_rendering(self):
        text = self.engine.explain("SELECT * FROM users WHERE city = 'bj'")
        self.assertIn("Filter[city = 'bj']", text)


if __name__ == "__main__":
    unittest.main()
