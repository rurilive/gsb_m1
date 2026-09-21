"""depsolve 解析器防回归测试。

运行方式: python3 -m unittest discover -s tests -v
"""

import unittest

from depsolve import (
    CircularDependencyError,
    ConflictError,
    UnknownPackageError,
    resolve,
)


def make_manifest():
    return {
        "unicode": {"versions": ["1.0.0"]},
        "fmt": {"versions": ["1.1.0", "1.2.0"], "depends": ["unicode>=0.9"]},
        "json": {"versions": ["1.1.0", "2.0.1", "2.1.0"], "depends": ["unicode>=0.5"]},
        "cli": {"versions": ["1.0.0"], "depends": ["fmt>=1.0", "json>=2.0"]},
        "gateway": {"versions": ["1.0.0"], "depends": ["json>=2.0", "oldcache"]},
        "oldcache": {"versions": ["0.9.0"], "depends": ["json<2.0"]},
        "archive": {"versions": ["1.0.0"], "depends": ["json>=2.0"],
                    "optional_depends": ["archive-sse"]},
        "archive-sse": {"versions": ["0.2.0"], "depends": ["archive>=1.0"]},
    }


class TopologicalOrderTest(unittest.TestCase):
    def test_dependencies_come_first(self):
        order = resolve(make_manifest(), ["cli"])
        self.assertEqual(
            order,
            ["unicode@1.0.0", "fmt@1.2.0", "json@2.1.0", "cli@1.0.0"],
        )

    def test_highest_version_satisfying_all_constraints(self):
        manifest = make_manifest()
        manifest["app"] = {"versions": ["1.0.0"], "depends": ["json>=2.0,<2.1"]}
        order = resolve(manifest, ["app"])
        self.assertIn("json@2.0.1", order)


class SelfDependencyTest(unittest.TestCase):
    def test_plain_self_dependency_is_circular(self):
        manifest = {"bad": {"versions": ["1.0.0"], "depends": ["bad"]}}
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["bad"])
        self.assertIn("bad -> bad", str(ctx.exception))

    def test_constrained_self_dependency_is_circular(self):
        manifest = {"bad": {"versions": ["1.0.0"], "depends": ["bad>=1.0"]}}
        with self.assertRaises(CircularDependencyError):
            resolve(manifest, ["bad"])

    def test_indirect_cycle_is_circular(self):
        manifest = {
            "a": {"versions": ["1.0.0"], "depends": ["b"]},
            "b": {"versions": ["1.0.0"], "depends": ["a"]},
        }
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["a"])
        self.assertIn("a -> b -> a", str(ctx.exception))


class DeterminismTest(unittest.TestCase):
    def test_repeated_resolution_is_identical(self):
        manifest = make_manifest()
        first = resolve(manifest, ["cli", "archive"])
        for _ in range(20):
            self.assertEqual(resolve(manifest, ["cli", "archive"]), first)

    def test_duplicate_requests_are_ignored(self):
        manifest = make_manifest()
        self.assertEqual(
            resolve(manifest, ["cli", "cli"]),
            resolve(manifest, ["cli"]),
        )


class OptionalDependsTest(unittest.TestCase):
    def test_optional_group_excluded_when_not_enabled(self):
        order = resolve(make_manifest(), ["archive"])
        self.assertEqual(
            order,
            ["unicode@1.0.0", "json@2.1.0", "archive@1.0.0"],
        )

    def test_optional_group_included_when_enabled(self):
        with self.assertRaises(CircularDependencyError):
            resolve(make_manifest(), ["archive"], enabled={"archive-sse"})

    def test_optional_group_resolves_when_enabled_and_acyclic(self):
        manifest = make_manifest()
        manifest["archive-sse"] = {"versions": ["0.2.0"]}
        order = resolve(manifest, ["archive"], enabled={"archive-sse"})
        self.assertEqual(
            order,
            ["unicode@1.0.0", "json@2.1.0", "archive-sse@0.2.0", "archive@1.0.0"],
        )


class ConflictTest(unittest.TestCase):
    def test_incompatible_constraints_raise_conflict(self):
        with self.assertRaises(ConflictError):
            resolve(make_manifest(), ["gateway"])

    def test_conflict_message_lists_requirers(self):
        with self.assertRaises(ConflictError) as ctx:
            resolve(make_manifest(), ["gateway"])
        message = str(ctx.exception)
        self.assertIn("gateway", message)
        self.assertIn("oldcache", message)

    def test_no_satisfying_version_raises_conflict(self):
        manifest = {
            "app": {"versions": ["1.0.0"], "depends": ["json>=9.0"]},
            "json": {"versions": ["2.1.0"]},
        }
        with self.assertRaises(ConflictError):
            resolve(manifest, ["app"])


class UnknownPackageTest(unittest.TestCase):
    def test_unknown_dependency(self):
        manifest = {"app": {"versions": ["1.0.0"], "depends": ["ghost"]}}
        with self.assertRaises(UnknownPackageError):
            resolve(manifest, ["app"])

    def test_unknown_root_request(self):
        with self.assertRaises(UnknownPackageError):
            resolve(make_manifest(), ["ghost"])


if __name__ == "__main__":
    unittest.main()
