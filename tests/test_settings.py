"""confy 现有行为的锁定测试（内置单层 dict 语义）。"""

import unittest

from confy import (
    CONFIG,
    MissingKeyError,
    child_keys,
    describe,
    export,
    get,
    is_branch,
    leaf_keys,
    missing,
    require,
    section,
)


class TestGet(unittest.TestCase):
    def test_leaf_value(self):
        self.assertEqual(get("db.port"), 5432)

    def test_default_on_missing(self):
        self.assertIsNone(get("nope.key"))
        self.assertEqual(get("nope.key", 42), 42)

    def test_branch_key_counts_as_missing(self):
        self.assertIsNone(get("db"))

    def test_types_preserved(self):
        self.assertIs(get("app.debug"), False)
        self.assertIsInstance(get("worker.concurrency"), int)
        self.assertIsInstance(get("db.options"), dict)
        self.assertEqual(get("worker.queues"), ["default", "mail"])


class TestRequire(unittest.TestCase):
    def test_returns_value(self):
        self.assertEqual(require("app.name"), "orders")

    def test_missing_raises(self):
        with self.assertRaises(MissingKeyError):
            require("nope.key")

    def test_is_keyerror(self):
        self.assertTrue(issubclass(MissingKeyError, KeyError))


class TestSection(unittest.TestCase):
    def test_subtree_without_prefix(self):
        self.assertEqual(
            section("db"),
            {
                "host": "127.0.0.1",
                "port": 5432,
                "pool_size": 8,
                "options": {"ssl": False, "timeout": 3.5},
            },
        )

    def test_returns_copy(self):
        s = section("worker")
        s["concurrency"] = 999
        self.assertEqual(CONFIG["worker.concurrency"], 4)

    def test_leaf_raises(self):
        with self.assertRaises(MissingKeyError):
            section("db.port")

    def test_unknown_raises(self):
        with self.assertRaises(MissingKeyError):
            section("nope")


class TestStore(unittest.TestCase):
    def test_leaf_keys_exclude_branches(self):
        keys = leaf_keys()
        self.assertIn("db.port", keys)
        self.assertNotIn("db", keys)

    def test_is_branch(self):
        self.assertTrue(is_branch("db"))
        self.assertFalse(is_branch("db.port"))

    def test_describe_lines(self):
        lines = describe()
        self.assertIn("db.port = 5432 (int)", lines)
        self.assertIn("app.debug = False (bool)", lines)

    def test_child_keys(self):
        self.assertEqual(child_keys("app"), ["name", "debug", "tags"])
        self.assertEqual(child_keys("nope"), [])

    def test_export_all_leaves(self):
        flat = export()
        self.assertEqual(flat["db.port"], 5432)
        self.assertNotIn("db", flat)
        # 拷贝：改返回值不影响内置配置
        flat["db.port"] = 1
        self.assertEqual(CONFIG["db.port"], 5432)

    def test_missing_lists_absent_keys(self):
        self.assertEqual(
            missing(["app.name", "nope.a", "nope.b"]),
            ["nope.a", "nope.b"],
        )


if __name__ == "__main__":
    unittest.main()
