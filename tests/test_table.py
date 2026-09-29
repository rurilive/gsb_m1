"""Table 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from columnkit.table import Table, select


ROWS = [
    {"id": 1, "city": "beijing", "amount": 30},
    {"id": 2, "city": "shanghai", "amount": 10},
    {"id": 3, "city": "beijing", "amount": 20},
]


class TestConstruction(unittest.TestCase):
    def test_name_and_columns(self):
        t = Table("orders", ROWS)
        self.assertEqual(t.name, "orders")
        self.assertEqual(t.columns, ("id", "city", "amount"))

    def test_columns_explicit(self):
        t = Table("orders", ROWS, columns=["amount", "id"])
        self.assertEqual(t.columns, ("amount", "id"))

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            Table("", ROWS)

    def test_non_dict_row_rejected(self):
        with self.assertRaises(ValueError):
            Table("orders", [(1, 2, 3)])


class TestRowsCopied(unittest.TestCase):
    def test_source_rows_not_aliased(self):
        source = [dict(ROWS[0])]
        t = Table("orders", source)
        source[0]["amount"] = 999
        self.assertEqual(t.to_dicts()[0]["amount"], 30)

    def test_iteration_yields_copies(self):
        t = Table("orders", ROWS)
        row = next(iter(t))
        row["amount"] = 999
        self.assertEqual(t.to_dicts()[0]["amount"], 30)


class TestFilter(unittest.TestCase):
    def test_filter_keeps_matching_rows(self):
        t = Table("orders", ROWS)
        out = t.filter(lambda r: r["city"] == "beijing")
        self.assertEqual([r["id"] for r in out], [1, 3])

    def test_filter_returns_table(self):
        t = Table("orders", ROWS)
        out = t.filter(lambda r: True)
        self.assertIsInstance(out, Table)
        self.assertEqual(out.name, "orders")
        self.assertEqual(out.columns, t.columns)

    def test_filter_does_not_mutate_source(self):
        t = Table("orders", ROWS)
        t.filter(lambda r: r["amount"] > 15)
        self.assertEqual(t.count(), 3)

    def test_filter_non_callable_rejected(self):
        t = Table("orders", ROWS)
        with self.assertRaises(ValueError):
            t.filter(5)

    def test_count(self):
        t = Table("orders", ROWS)
        self.assertEqual(t.count(), 3)

    def test_select_function(self):
        t = Table("orders", ROWS)
        out = select(t, lambda r: r["amount"] < 25)
        self.assertEqual([r["id"] for r in out], [2, 3])

    def test_select_non_table_rejected(self):
        with self.assertRaises(ValueError):
            select([], lambda r: True)


if __name__ == "__main__":
    unittest.main()
