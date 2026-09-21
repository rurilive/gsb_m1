import unittest

from logpipe.paths import (
    PathError,
    format_path,
    get_path,
    parse_path,
    set_path,
    walk_leaves,
)


class ParsePathTests(unittest.TestCase):
    def test_plain_keys(self):
        self.assertEqual(
            parse_path("user.phone"),
            [("key", "user"), ("key", "phone")],
        )

    def test_indices(self):
        self.assertEqual(
            parse_path("payments[0].card"),
            [("key", "payments"), ("index", 0), ("key", "card")],
        )
        self.assertEqual(
            parse_path("grid[1][2]"),
            [("key", "grid"), ("index", 1), ("index", 2)],
        )

    def test_digits_with_leading_zero(self):
        self.assertEqual(parse_path("rows[00]"), [("key", "rows"), ("index", 0)])

    def test_malformed_paths(self):
        bad = [
            "",
            "user.",
            ".user",
            "a..b",
            "payments[x]",
            "payments[]",
            "payments[1",
            "payments[1]]",
            "payments[-1]",
            "payments[0]x",
            "a]b",
        ]
        for path in bad:
            with self.subTest(path=path):
                with self.assertRaises(PathError):
                    parse_path(path)

    def test_non_string(self):
        with self.assertRaises(PathError):
            parse_path(None)
        with self.assertRaises(PathError):
            parse_path(3)


class FormatPathTests(unittest.TestCase):
    def test_round_trip(self):
        for path in ["user.phone", "payments[0].card", "grid[1][2]", "a[0].b[1].c"]:
            with self.subTest(path=path):
                self.assertEqual(format_path(parse_path(path)), path)


class GetPathTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "user": {"name": "amy", "phone": "13812345678"},
            "payments": [
                {"card": "6222", "amount": 12.5},
                {"card": "2333", "amount": 3},
            ],
        }

    def test_nested_lookup(self):
        self.assertEqual(get_path(self.record, "user.name"), "amy")
        self.assertEqual(get_path(self.record, "payments[1].card"), "2333")
        self.assertEqual(get_path(self.record, "payments[0].amount"), 12.5)

    def test_missing_key(self):
        with self.assertRaises(PathError):
            get_path(self.record, "user.email")

    def test_index_out_of_range(self):
        with self.assertRaises(PathError):
            get_path(self.record, "payments[2].card")

    def test_wrong_container(self):
        with self.assertRaises(PathError):
            get_path(self.record, "user[0]")
        with self.assertRaises(PathError):
            get_path(self.record, "payments.card")

    def test_key_and_index_are_distinct(self):
        record = {"rows": {"0": "zero"}, "list": ["item"]}
        self.assertEqual(get_path(record, "rows.0"), "zero")
        self.assertEqual(get_path(record, "list[0]"), "item")
        with self.assertRaises(PathError):
            get_path(record, "rows[0]")
        with self.assertRaises(PathError):
            get_path(record, "list.0")

    def test_default(self):
        self.assertEqual(get_path(self.record, "user.email", default=None), None)
        self.assertEqual(get_path(self.record, "user.email", default="?"), "?")


class SetPathTests(unittest.TestCase):
    def test_replace_key(self):
        record = {"user": {"name": "amy"}}
        set_path(record, "user.name", "bob")
        self.assertEqual(record["user"]["name"], "bob")

    def test_replace_list_item(self):
        record = {"payments": [{"amount": 1}, {"amount": 2}]}
        set_path(record, "payments[1].amount", 9)
        self.assertEqual(record["payments"][1]["amount"], 9)

    def test_missing_target_is_rejected(self):
        record = {"user": {"name": "amy"}}
        with self.assertRaises(PathError):
            set_path(record, "user.email", "x")
        with self.assertRaises(PathError):
            set_path(record, "payments[0]", 1)

    def test_out_of_range_is_rejected(self):
        record = {"payments": []}
        with self.assertRaises(PathError):
            set_path(record, "payments[0]", 1)


class WalkLeavesTests(unittest.TestCase):
    def test_order_and_paths(self):
        record = {
            "user": {"name": "amy", "tags": []},
            "grid": [[1, 2], [3]],
            "ok": True,
        }
        leaves = list(walk_leaves(record))
        self.assertEqual(
            [path for path, _ in leaves],
            ["user.name", "grid[0][0]", "grid[0][1]", "grid[1][0]", "ok"],
        )
        self.assertEqual([value for _, value in leaves], ["amy", 1, 2, 3, True])

    def test_empty_and_scalar_records(self):
        self.assertEqual(list(walk_leaves({})), [])
        self.assertEqual(list(walk_leaves({"a": []})), [])
        self.assertEqual(list(walk_leaves({"a": {}})), [])

    def test_none_is_a_leaf(self):
        self.assertEqual(list(walk_leaves({"a": None})), [("a", None)])


if __name__ == "__main__":
    unittest.main()
