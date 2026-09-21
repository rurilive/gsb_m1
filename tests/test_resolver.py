"""depsolve 回归测试：覆盖四个已修复缺陷及基本解析语义。"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from depsolve import (
    CircularDependencyError,
    ConflictError,
    UnknownPackageError,
    resolve,
)

MANIFEST = {
    "unicode":    {"versions": ["1.0.0"]},
    "fmt":        {"versions": ["1.1.0", "1.2.0"], "depends": ["unicode>=0.9"]},
    "json":       {"versions": ["1.1.0", "2.0.1", "2.1.0"], "depends": ["unicode>=0.5"]},
    "cli":        {"versions": ["1.0.0"], "depends": ["fmt>=1.0", "json>=2.0"]},
    "gateway":    {"versions": ["1.0.0"], "depends": ["json>=2.0", "oldcache"]},
    "oldcache":   {"versions": ["0.9.0"], "depends": ["json<2.0"]},
    "archive":    {"versions": ["1.0.0"], "depends": ["json>=2.0"],
                   "optional_depends": ["archive-sse"]},
    "archive-sse": {"versions": ["0.2.0"], "depends": ["archive>=1.0"]},
}


def names(order):
    return [item.split("@")[0] for item in order]


class TestCircularDependency(unittest.TestCase):

    def test_self_dependency_raises(self):
        manifest = {"a": {"versions": ["1.0.0"], "depends": ["a"]}}
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["a"])
        self.assertIn("a -> a", str(ctx.exception))

    def test_self_dependency_with_constraint_raises(self):
        manifest = {"a": {"versions": ["1.0.0"], "depends": ["a>=1.0"]}}
        with self.assertRaises(CircularDependencyError):
            resolve(manifest, ["a"])

    def test_indirect_cycle_raises_with_chain(self):
        manifest = {
            "a": {"versions": ["1.0.0"], "depends": ["b"]},
            "b": {"versions": ["1.0.0"], "depends": ["c"]},
            "c": {"versions": ["1.0.0"], "depends": ["a"]},
        }
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["a"])
        self.assertIn("a -> b -> c -> a", str(ctx.exception))


class TestDeterminism(unittest.TestCase):

    def test_repeated_resolve_is_identical(self):
        first = resolve(MANIFEST, ["cli", "archive"])
        for _ in range(5):
            self.assertEqual(first, resolve(MANIFEST, ["cli", "archive"]))

    def test_stable_across_hash_seeds(self):
        script = (
            "import sys; sys.path.insert(0, '.');"
            "from tests.test_resolver import MANIFEST;"
            "from depsolve import resolve;"
            "print('\\n'.join(resolve(MANIFEST, ['archive', 'cli'])))"
        )
        outputs = []
        for seed in ("0", "1", "42"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env, check=True,
                cwd=os.path.join(os.path.dirname(__file__), ".."),
            )
            outputs.append(out.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])


class TestOptionalDepends(unittest.TestCase):

    def test_disabled_optional_group_not_in_graph(self):
        order = resolve(MANIFEST, ["archive"])
        self.assertEqual(names(order), ["unicode", "json", "archive"])

    def test_disabled_optional_group_does_not_trigger_cycle(self):
        # archive-sse 依赖 archive，未启用时不应报循环依赖
        resolve(MANIFEST, ["archive"])

    def test_enabled_optional_group_participates(self):
        with self.assertRaises(CircularDependencyError):
            resolve(MANIFEST, ["archive"], enabled={"archive-sse"})

    def test_enabled_acyclic_optional_group_resolves(self):
        manifest = {
            "app":   {"versions": ["1.0.0"], "optional_depends": ["accel"]},
            "accel": {"versions": ["0.2.0"]},
        }
        self.assertEqual(names(resolve(manifest, ["app"])), ["app"])
        self.assertEqual(
            names(resolve(manifest, ["app"], enabled={"accel"})),
            ["accel", "app"],
        )


class TestVersionConflicts(unittest.TestCase):

    def test_conflicting_constraints_raise(self):
        with self.assertRaises(ConflictError):
            resolve(MANIFEST, ["gateway"])

    def test_highest_version_satisfying_all_constraints(self):
        manifest = {
            "lib": {"versions": ["1.0.0", "1.5.0", "2.0.0"]},
            "a":   {"versions": ["1.0.0"], "depends": ["lib>=1.0"]},
            "b":   {"versions": ["1.0.0"], "depends": ["lib<2.0"]},
        }
        order = resolve(manifest, ["a", "b"])
        self.assertIn("lib@1.5.0", order)

    def test_no_constraint_picks_highest(self):
        self.assertIn("json@2.1.0", resolve(MANIFEST, ["cli"]))


class TestBasicSemantics(unittest.TestCase):

    def test_topological_order(self):
        order = names(resolve(MANIFEST, ["cli"]))
        self.assertLess(order.index("unicode"), order.index("fmt"))
        self.assertLess(order.index("fmt"), order.index("cli"))
        self.assertLess(order.index("json"), order.index("cli"))

    def test_unknown_package_raises(self):
        with self.assertRaises(UnknownPackageError):
            resolve(MANIFEST, ["cli", "ghost"])

    def test_duplicate_requests_resolved_once(self):
        order = resolve(MANIFEST, ["cli", "cli"])
        self.assertEqual(len(names(order)), len(set(names(order))))


if __name__ == "__main__":
    unittest.main()
