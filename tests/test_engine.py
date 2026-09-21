"""Engine 行为基线：判定、批量、改授权立刻生效。"""

import unittest

from rbacflow import Engine, InvalidAction, PolicyStore, UnknownRole


class EngineCase(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("viewer", "editor", "admin"):
            self.store.declare(role)
        self.store.grant("viewer", "docs:read")
        self.store.grant("editor", "docs:read")
        self.store.grant("editor", "docs:write")
        self.store.grant("admin", "pkg:write")
        self.engine = Engine(self.store)


class TestCheck(EngineCase):

    def test_exact_hit_and_miss(self):
        self.assertTrue(self.engine.check("editor", "docs:write"))
        self.assertFalse(self.engine.check("viewer", "docs:write"))

    def test_missing_namespace_is_not_a_hit(self):
        self.assertFalse(self.engine.check("viewer", "docs"))
        self.assertFalse(self.engine.check("viewer", "docs:read:draft"))
        self.assertFalse(self.engine.check("viewer", "pkg:read"))

    def test_unknown_role(self):
        with self.assertRaises(UnknownRole):
            self.engine.check("ghost", "docs:read")

    def test_invalid_action(self):
        with self.assertRaises(InvalidAction):
            self.engine.check("editor", "docs:Write!")
        with self.assertRaises(InvalidAction):
            self.engine.check("editor", "")

    def test_check_many_keeps_order(self):
        got = self.engine.check_many("editor", ["pkg:write", "docs:read", "docs:write"])
        self.assertEqual(list(got.items()),
                         [("pkg:write", False), ("docs:read", True), ("docs:write", True)])

    def test_permitted_is_grant_order(self):
        self.assertEqual(self.engine.permitted("editor"), ["docs:read", "docs:write"])


class TestLiveUpdates(EngineCase):

    def test_grant_is_visible_on_next_check(self):
        self.assertFalse(self.engine.check("viewer", "pkg:write"))
        self.store.grant("viewer", "pkg:write")
        self.assertTrue(self.engine.check("viewer", "pkg:write"))

    def test_revoke_is_visible_on_next_check(self):
        self.assertTrue(self.engine.check("editor", "docs:write"))
        self.store.revoke("editor", "docs:write")
        self.assertFalse(self.engine.check("editor", "docs:write"))

    def test_undeclared_role_still_unknown(self):
        with self.assertRaises(UnknownRole):
            self.engine.check("ghost", "docs:read")
        self.store.declare("ghost")
        self.assertFalse(self.engine.check("ghost", "docs:read"))

    def test_two_engines_share_one_store(self):
        other = Engine(self.store)
        self.store.grant("admin", "docs:read")
        self.assertTrue(other.check("admin", "docs:read"))
        self.assertTrue(self.engine.check("admin", "docs:read"))


if __name__ == "__main__":
    unittest.main()
