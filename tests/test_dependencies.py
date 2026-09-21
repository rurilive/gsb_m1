"""requires 依赖声明、按序初始化与一致性报告。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from replug import ManifestError, PluginRuntime  # noqa: E402
from replug.manifest import parse_manifest  # noqa: E402
from replug.runtime import topo_order  # noqa: E402


class RequiresManifestTest(unittest.TestCase):
    def test_requires_defaults_to_empty_tuple(self):
        manifest = parse_manifest({"name": "a", "version": "1.0.0"},
                                  "a", "a.py")
        self.assertEqual(manifest.requires, ())

    def test_requires_list_is_kept_as_tuple(self):
        manifest = parse_manifest(
            {"name": "a", "version": "1.0.0",
             "requires": ["b", "c", "b"]}, "a", "a.py")
        self.assertEqual(manifest.requires, ("b", "c", "b"))

    def test_bad_requires_is_rejected(self):
        for bad in ("b", ["b", 1], [""], {"b": 1}, 7, True):
            with self.assertRaises(ManifestError):
                parse_manifest(
                    {"name": "a", "version": "1.0.0", "requires": bad},
                    "a", "a.py")


def manifest_for(name, requires=()):
    from replug.manifest import PluginManifest
    return PluginManifest(name, "1.0.0", requires=requires)


class TopoOrderTest(unittest.TestCase):
    def test_dependencies_come_first(self):
        manifests = {
            "a": manifest_for("a", ["b", "c"]),
            "b": manifest_for("b", ["c"]),
            "c": manifest_for("c"),
        }
        order = topo_order(manifests)
        self.assertLess(order.index("c"), order.index("b"))
        self.assertLess(order.index("b"), order.index("a"))

    def test_independent_plugins_break_ties_by_name(self):
        manifests = {name: manifest_for(name)
                     for name in ("zeta", "alpha", "mid")}
        self.assertEqual(topo_order(manifests), ["alpha", "mid", "zeta"])

    def test_self_and_missing_dependencies_are_rejected(self):
        with self.assertRaises(ManifestError):
            topo_order({"a": manifest_for("a", ["a"])})
        with self.assertRaises(ManifestError):
            topo_order({"a": manifest_for("a", ["ghost"])})

    def test_dependency_cycle_is_rejected(self):
        manifests = {
            "a": manifest_for("a", ["b"]),
            "b": manifest_for("b", ["a"]),
        }
        with self.assertRaises(ManifestError):
            topo_order(manifests)
        manifests = {
            "a": manifest_for("a", ["b"]),
            "b": manifest_for("b", ["c"]),
            "c": manifest_for("c", ["a"]),
        }
        with self.assertRaises(ManifestError):
            topo_order(manifests)


class DependencyLoadingTest(support.RuntimeTestCase):
    def _write_logging_plugin(self, name, requires=()):
        log_path = os.path.join(self.plugins.path, "_init.log")
        extra = ('"requires": [%s]' % ", ".join(repr(r) for r in requires)
                 if requires else "")
        self.plugins.write(
            name, manifest_extra=extra,
            init_body="with open(%r, 'a', encoding='utf-8') as log: "
                      "log.write(%r + '\\n')" % (log_path, name),
            handle_body="return request")

    def _init_log(self):
        with open(os.path.join(self.plugins.path, "_init.log"),
                  encoding="utf-8") as stream:
            return [line for line in stream.read().splitlines() if line]

    def test_load_all_initializes_in_dependency_order(self):
        self._write_logging_plugin("a", requires=["b", "c"])
        self._write_logging_plugin("b", requires=["c"])
        self._write_logging_plugin("c")
        runtime = PluginRuntime(self.plugins.path)
        self.assertEqual(runtime.load_all(), ["a", "b", "c"])
        order = self._init_log()
        self.assertEqual(order[0], "c")
        self.assertLess(order.index("c"), order.index("b"))
        self.assertLess(order.index("b"), order.index("a"))

    def test_requests_can_reach_dependencies(self):
        self.plugins.write("base", handle_body="return 'base:' + request")
        self.plugins.write(
            "front", manifest_extra='"requires": ["base"]',
            handle_body="return 'front:' + request")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.assertEqual(runtime.request("base", "x"), "base:x")
        self.assertEqual(runtime.request("front", "y"), "front:y")

    def test_missing_required_plugin_aborts_whole_load(self):
        self.plugins.write("a", version="1.0.0",
                           manifest_extra='"requires": ["ghost"]')
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(ManifestError):
            runtime.load_all()
        self.assertEqual(runtime.plugin_names(), [])

    def test_dependency_cycle_aborts_whole_load(self):
        self.plugins.write("a", manifest_extra='"requires": ["b"]')
        self.plugins.write("b", manifest_extra='"requires": ["a"]')
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(ManifestError):
            runtime.load_all()
        self.assertEqual(runtime.plugin_names(), [])


class ConsistencyReportTest(support.RuntimeTestCase):
    def _load_chain(self):
        self.plugins.write("c", handle_body="return PLUGIN['version']")
        self.plugins.write("b", manifest_extra='"requires": ["c"]',
                           handle_body="return PLUGIN['version']")
        self.plugins.write("a", manifest_extra='"requires": ["b"]',
                           handle_body="return PLUGIN['version']")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        return runtime

    def test_all_consistent_after_load_all(self):
        runtime = self._load_chain()
        self.assertEqual(runtime.consistency_report(),
                         {"a": [], "b": [], "c": []})

    def test_reloading_dependency_flags_dependents_but_keeps_them_serving(self):
        runtime = self._load_chain()
        self.plugins.write("c", version="2.0.0",
                           handle_body="return PLUGIN['version']")
        runtime.reload("c")
        self.assertEqual(runtime.consistency_report(),
                         {"a": ["c"], "b": ["c"], "c": []})
        # 被依赖者重载，依赖方版本与状态纹丝不动
        self.assertEqual(runtime.version_of("b"), "1.0.0")
        self.assertEqual(runtime.version_of("a"), "1.0.0")

    def test_transitive_chain_reloaded_level_by_level(self):
        runtime = self._load_chain()
        self.plugins.write("c", version="2.0.0",
                           handle_body="return PLUGIN['version']")
        runtime.reload("c")
        self.plugins.write("b", version="2.0.0",
                           manifest_extra='"requires": ["c"]',
                           handle_body="return PLUGIN['version']")
        runtime.reload("b")
        self.assertEqual(runtime.consistency_report(),
                         {"a": ["b", "c"], "b": [], "c": []})
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["b"]',
                           handle_body="return PLUGIN['version']")
        runtime.reload("a")
        self.assertEqual(runtime.consistency_report(),
                         {"a": [], "b": [], "c": []})

    def test_reloading_dependent_does_not_touch_dependency(self):
        runtime = self._load_chain()
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["b"]',
                           handle_body="return PLUGIN['version']")
        runtime.reload("a")
        self.assertEqual(runtime.consistency_report(),
                         {"a": [], "b": [], "c": []})
        self.assertEqual(runtime.version_of("c"), "1.0.0")

    def test_full_reload_clears_inconsistency(self):
        runtime = self._load_chain()
        self.plugins.write("c", version="2.0.0",
                           handle_body="return PLUGIN['version']")
        runtime.reload("c")
        self.plugins.write("b", version="2.0.0",
                           manifest_extra='"requires": ["c"]',
                           handle_body="return PLUGIN['version']")
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["b"]',
                           handle_body="return PLUGIN['version']")
        runtime.load_all()
        self.assertEqual(runtime.consistency_report(),
                         {"a": [], "b": [], "c": []})


if __name__ == "__main__":
    unittest.main()
