"""WHERE 复合条件与等值下推的行为测试。

覆盖：AND/OR 与括号任意嵌套（AND 优先级高于 OR），以及 build_plan
里的等值条件下推——explain 与执行共用同一份计划，故 explain 的
层叠顺序即为求值顺序。
"""

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

    def names(self, cond):
        return [r["name"] for r in
                self.engine.execute("SELECT name FROM users WHERE " + cond)]

    def test_and_basic(self):
        self.assertEqual(self.names("city = 'bj' AND age > 30"),
                         ["alice", "carol"])

    def test_or_basic(self):
        self.assertEqual(self.names("age < 25 OR age > 40"),
                         ["carol", "erin"])

    def test_and_has_higher_precedence_than_or(self):
        # 等价于 city='sh' OR (age=28 AND dept='edge')
        self.assertEqual(self.names("city = 'sh' OR age = 28 AND dept = 'edge'"),
                         ["bob", "dave"])

    def test_parentheses_change_grouping(self):
        # 括号把 OR 先组合，再与 AND 相交，只剩 bob
        self.assertEqual(self.names("(city = 'sh' OR age = 28) AND dept = 'core'"),
                         [])

    def test_nested_or_inside_and(self):
        self.assertEqual(self.names("dept = 'core' AND (age > 40 OR age < 25)"),
                         ["carol", "erin"])

    def test_nested_and_inside_or(self):
        self.assertEqual(self.names("age > 100 OR (city = 'bj' AND age = 34)"),
                         ["alice"])

    def test_deeply_nested_parentheses(self):
        cond = "((age = 28 OR age = 22) AND (city = 'gz' OR city = 'bj'))"
        self.assertEqual(self.names(cond), ["dave", "erin"])

    def test_redundant_parentheses_around_single_condition(self):
        self.assertEqual(self.names("(age >= 41)"), ["carol"])

    def test_missing_right_paren(self):
        with self.assertRaises(ParseError):
            self.names("(age = 28 OR age = 22")

    def test_dangling_operator(self):
        with self.assertRaises(ParseError):
            self.names("age = 28 AND")

    def test_empty_parentheses(self):
        with self.assertRaises(ParseError):
            self.names("()")

    def test_and_or_are_reserved_words(self):
        with self.assertRaises(ParseError):
            self.engine.execute("SELECT and FROM users")


class TestNestedExplain(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_explain_shows_nested_condition_tree(self):
        text = self.engine.explain(
            "SELECT name FROM users "
            "WHERE dept = 'core' AND (age > 40 OR city = 'bj' AND age < 25)")
        # 顶层 AND 摊平后等值项下推，剩余子树保留嵌套结构
        self.assertEqual(text.splitlines(), [
            "Project[cols=name]",
            "  Filter[OR(age > 40, AND(city = 'bj', age < 25))]",
            "    Filter[dept = 'core']",
            "      SeqScan[table=users]",
        ])

    def test_explain_or_render(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE age < 25 OR age > 40")
        self.assertIn("Filter[OR(age < 25, age > 40)]", text)


class TestEqualityPushdown(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def test_equality_filter_below_range_filter(self):
        text = self.engine.explain(
            "SELECT name FROM users WHERE city = 'bj' AND age > 30")
        self.assertEqual(text.splitlines(), [
            "Project[cols=name]",
            "  Filter[age > 30]",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ])

    def test_pushdown_preserves_relative_order(self):
        # 两个剩余条件保持出现先后；两个等值条件也保持先后并同层 AND
        text = self.engine.explain(
            "SELECT * FROM users "
            "WHERE age >= 20 AND city = 'bj' AND age < 40 AND dept = 'core'")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[AND(age >= 20, age < 40)]",
            "    Filter[AND(city = 'bj', dept = 'core')]",
            "      SeqScan[table=users]",
        ])

    def test_only_equalities_single_filter_on_scan(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND age = 34")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[AND(city = 'bj', age = 34)]",
            "    SeqScan[table=users]",
        ])

    def test_no_equalities_single_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE age > 20 AND age < 40")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[AND(age > 20, age < 40)]",
            "    SeqScan[table=users]",
        ])

    def test_single_equality_stays_single_compare_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE city = 'bj'")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[city = 'bj']",
            "    SeqScan[table=users]",
        ])

    def test_single_non_equality_stays_single_compare_filter(self):
        text = self.engine.explain("SELECT * FROM users WHERE age > 40")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[age > 40]",
            "    SeqScan[table=users]",
        ])

    def test_top_level_or_not_split(self):
        # 顶层不是 AND，不做下推，OR 整体一层
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' OR age = 28")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[OR(city = 'bj', age = 28)]",
            "    SeqScan[table=users]",
        ])

    def test_and_inside_or_subtree_untouched(self):
        # 顶层 OR 不动；其 AND 子树内的等值不被拆出
        text = self.engine.explain(
            "SELECT * FROM users WHERE age > 40 OR (city = 'bj' AND age = 28)")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[OR(age > 40, AND(city = 'bj', age = 28))]",
            "    SeqScan[table=users]",
        ])

    def test_nested_and_is_flattened_at_top_level(self):
        # (A AND B) AND (C OR D)：顶层 AND 摊平，等值 A 下推，B 与 OR 同层
        text = self.engine.explain(
            "SELECT name FROM users "
            "WHERE (city = 'bj' AND age >= 20) AND (dept = 'x' OR age < 25)")
        self.assertEqual(text.splitlines(), [
            "Project[cols=name]",
            "  Filter[AND(age >= 20, OR(dept = 'x', age < 25))]",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ])

    def test_ne_kept_in_remaining_filter(self):
        text = self.engine.explain(
            "SELECT * FROM users WHERE city = 'bj' AND dept != 'core'")
        self.assertEqual(text.splitlines(), [
            "Project[cols=*]",
            "  Filter[dept != 'core']",
            "    Filter[city = 'bj']",
            "      SeqScan[table=users]",
        ])


class TestPushdownExecution(unittest.TestCase):
    def setUp(self):
        self.engine = fresh_engine()

    def names(self, cond):
        return [r["name"] for r in
                self.engine.execute("SELECT name FROM users WHERE " + cond)]

    def test_results_unchanged_after_pushdown(self):
        self.assertEqual(self.names("city = 'bj' AND age > 30"),
                         ["alice", "carol"])
        self.assertEqual(
            self.names("dept = 'core' AND age >= 20 AND (city = 'sh' OR age < 25)"),
            ["erin"])

    def test_missing_column_in_equality_still_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM users WHERE tel = 1")

    def test_missing_column_in_remaining_still_keyerror(self):
        with self.assertRaises(KeyError):
            self.engine.execute("SELECT * FROM users WHERE city = 'bj' AND tel > 1")

    def test_stable_order_after_pushdown(self):
        # bob/dave 同为 28，过滤后保持注册先后
        self.assertEqual(
            self.names("dept = 'edge' AND age = 28"), ["bob", "dave"])


if __name__ == "__main__":
    unittest.main()
