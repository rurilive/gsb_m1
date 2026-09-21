"""PolicyStore 行为基线：声明、授予、撤销、展开与错误类型。"""

import unittest

from rbacflow import (
    DuplicateGrant,
    InvalidAction,
    NotGranted,
    PolicyError,
    PolicyStore,
    UnknownRole,
)


class StoreCase(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("viewer", "editor", "auditor"):
            self.store.declare(role)


class TestDeclare(StoreCase):

    def test_roles_keep_declaration_order(self):
        self.assertEqual(self.store.roles(), ["viewer", "editor", "auditor"])
        self.assertTrue(self.store.has_role("editor"))
        self.assertFalse(self.store.has_role("ghost"))

    def test_redeclare_is_noop(self):
        self.store.declare("viewer")
        self.assertEqual(self.store.roles(), ["viewer", "editor", "auditor"])

    def test_empty_role_name_rejected(self):
        with self.assertRaises(PolicyError):
            self.store.declare("")

    def test_role_names_are_not_normalized(self):
        self.store.declare("Viewer")
        self.assertEqual(self.store.roles(),
                         ["viewer", "editor", "auditor", "Viewer"])


class TestGrant(StoreCase):

    def test_granted_keeps_grant_order(self):
        for action in ("pkg:list", "docs:read", "docs:write"):
            self.store.grant("editor", action)
        self.assertEqual(self.store.granted("editor"),
                         ["pkg:list", "docs:read", "docs:write"])

    def test_grant_unknown_role(self):
        with self.assertRaises(UnknownRole):
            self.store.grant("ghost", "docs:read")

    def test_duplicate_grant_rejected(self):
        self.store.grant("editor", "docs:read")
        with self.assertRaises(DuplicateGrant):
            self.store.grant("editor", "docs:read")

    def test_grant_validates_action(self):
        for bad in ("", "Docs:read", ":docs", "docs:", "docs::read",
                    "docs read", "9docs:read", "docs.read"):
            with self.assertRaises(InvalidAction):
                self.store.grant("editor", bad)

    def test_granted_on_unknown_role(self):
        with self.assertRaises(UnknownRole):
            self.store.granted("ghost")


class TestRevoke(StoreCase):

    def test_revoke_takes_effect(self):
        self.store.grant("editor", "docs:write")
        self.store.revoke("editor", "docs:write")
        self.assertEqual(self.store.granted("editor"), [])

    def test_revoke_missing_grant(self):
        with self.assertRaises(NotGranted):
            self.store.revoke("editor", "docs:write")

    def test_revoke_unknown_role(self):
        with self.assertRaises(UnknownRole):
            self.store.revoke("ghost", "docs:write")


class TestLookup(StoreCase):

    def test_allowed_matches_exactly(self):
        self.store.grant("editor", "docs:read")
        self.assertTrue(self.store.allowed("editor", "docs:read"))
        self.assertFalse(self.store.allowed("editor", "docs:write"))
        self.assertFalse(self.store.allowed("editor", "docs:read:draft"))

    def test_allowed_ignores_other_roles(self):
        self.store.grant("editor", "docs:write")
        self.assertFalse(self.store.allowed("viewer", "docs:write"))

    def test_allowed_unknown_role(self):
        with self.assertRaises(UnknownRole):
            self.store.allowed("ghost", "docs:read")


class TestSummary(StoreCase):

    def test_rules_expand_in_declaration_and_grant_order(self):
        self.store.grant("auditor", "docs:read")
        self.store.grant("viewer", "pkg:list")
        self.store.grant("viewer", "docs:read")
        self.assertEqual(self.store.rules(), [
            ("viewer", "pkg:list"),
            ("viewer", "docs:read"),
            ("auditor", "docs:read"),
        ])

    def test_stats_counts(self):
        self.store.grant("editor", "docs:read")
        self.store.grant("editor", "docs:write")
        self.store.grant("auditor", "docs:read")
        stats = self.store.stats()
        self.assertEqual(stats["roles"], 3)
        self.assertEqual(stats["grants"], 3)

    def test_stats_after_revoke(self):
        self.store.grant("editor", "docs:read")
        self.store.revoke("editor", "docs:read")
        self.assertEqual(self.store.stats()["grants"], 0)


if __name__ == "__main__":
    unittest.main()
