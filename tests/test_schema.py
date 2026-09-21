"""列定义与行校验的既有行为锁定。"""

import unittest

from colpage.errors import SchemaError
from colpage.schema import INT64_MAX, Schema


def sample_schema():
    return Schema([("id", "int"), ("city", "str"), ("amount", "int")])


class SchemaTest(unittest.TestCase):
    def test_names_kinds_and_columns(self):
        schema = sample_schema()
        self.assertEqual(schema.names, ["id", "city", "amount"])
        self.assertEqual(schema.columns, [("id", "int"), ("city", "str"), ("amount", "int")])
        self.assertEqual(len(schema), 3)
        self.assertEqual(schema.kind("city"), "str")
        self.assertEqual(schema.index("amount"), 2)
        with self.assertRaises(SchemaError):
            schema.index("nope")
        self.assertEqual(schema, sample_schema())
        self.assertNotEqual(schema, Schema([("id", "int")]))

    def test_malformed_columns_rejected(self):
        with self.assertRaises(SchemaError):
            Schema([("a", "int"), ("a", "str")])
        with self.assertRaises(SchemaError):
            Schema([("a", "float")])
        with self.assertRaises(SchemaError):
            Schema([("a",)])
        with self.assertRaises(SchemaError):
            Schema([("", "int")])
        with self.assertRaises(SchemaError):
            Schema([42])

    def test_validate_row_accepts_well_formed_rows(self):
        schema = sample_schema()
        schema.validate_row({"id": 1, "city": "北京", "amount": -3})
        schema.validate_row({"id": INT64_MAX, "city": "", "amount": -(1 << 63)})

    def test_validate_row_rejects_missing_and_extra_keys(self):
        schema = sample_schema()
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": 1, "city": "北京"})
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": 1, "city": "北京", "amount": 2, "note": "x"})

    def test_validate_row_rejects_wrong_types(self):
        schema = sample_schema()
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": "1", "city": "北京", "amount": 2})
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": 1.5, "city": "北京", "amount": 2})
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": 1, "city": 7, "amount": 2})
        with self.assertRaises(SchemaError):
            schema.validate_row("id=1")

    def test_bool_is_not_an_int_value(self):
        schema = sample_schema()
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": True, "city": "北京", "amount": 2})

    def test_int64_range_enforced(self):
        schema = sample_schema()
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": INT64_MAX + 1, "city": "北京", "amount": 0})
        with self.assertRaises(SchemaError):
            schema.validate_row({"id": -(1 << 63) - 1, "city": "北京", "amount": 0})


if __name__ == "__main__":
    unittest.main()
