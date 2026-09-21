"""PluginRuntime 一次性装载路径的既有行为锁定。"""

import os
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from replug import (InitError, LoadError, ManifestError, PluginError,  # noqa: E402
                    PluginNotFound, PluginRuntime, ReplugError)
from replug.restart import restart_process  # noqa: E402

GREETER_BODY = '''\
state["hits"] += 1
return {"version": PLUGIN["version"], "hits": state["hits"],
        "who": request["who"]}
'''


class LoadTest(support.RuntimeTestCase):
    def test_load_all_loads_every_plugin_in_name_order(self):
        self.plugins.write("beta", version="0.3.0", init_body="return {}")
        self.plugins.write("alpha", version="1.2.0", init_body="return {}")
        runtime = PluginRuntime(self.plugins.path)
        self.assertEqual(runtime.load_all(), ["alpha", "beta"])
        self.assertEqual(runtime.plugin_names(), ["alpha", "beta"])
        self.assertEqual(runtime.version_of("alpha"), "1.2.0")
        self.assertEqual(runtime.version_of("beta"), "0.3.0")

    def test_loader_skips_dunder_and_private_files(self):
        self.plugins.write("alpha", init_body="return {}")
        self.plugins.write_source("__init__", "raise AssertionError('别读我')\n")
        self.plugins.write_source("_helper", "raise AssertionError('别读我')\n")
        runtime = PluginRuntime(self.plugins.path)
        self.assertEqual(runtime.load_all(), ["alpha"])

    def test_plugin_without_init_starts_with_none_state(self):
        self.plugins.write("plain", handle_body="return None")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.assertIsNone(runtime.state_of("plain"))
        self.assertIsNone(runtime.request("plain", {}))

    def test_init_can_read_its_context(self):
        self.plugins.write("alpha", init_body=(
            "return {'name': ctx.name, 'version': ctx.version}\n"))
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.assertEqual(runtime.state_of("alpha"),
                         {"name": "alpha", "version": "1.0.0"})

    def test_init_error_reports_name_and_leaves_nothing_loaded(self):
        self.plugins.write("alpha", init_body="return {}")
        self.plugins.write("beta", init_body="raise RuntimeError('炸了')")
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(InitError) as caught:
            runtime.load_all()
        self.assertIn("beta", str(caught.exception))
        self.assertEqual(runtime.plugin_names(), [])
        with self.assertRaises(PluginNotFound):
            runtime.request("alpha", {})

    def test_import_error_is_load_error(self):
        self.plugins.write_source("alpha", "def handle(state, request)\n")
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(LoadError):
            runtime.load_all()
        self.assertEqual(runtime.plugin_names(), [])

    def test_manifest_problems_are_reported(self):
        self.plugins.write_source(
            "alpha", 'PLUGIN = {"name": "beta", "version": "1.0.0"}\n')
        with self.assertRaises(ManifestError):
            PluginRuntime(self.plugins.path).load_all()

        self.plugins.write_source(
            "alpha", 'PLUGIN = {"name": "alpha", "version": "1.0.0"}\n')
        with self.assertRaises(ManifestError):
            PluginRuntime(self.plugins.path).load_all()

    def test_missing_plugin_dir_raises(self):
        runtime = PluginRuntime(os.path.join(self.plugins.path, "没有这个目录"))
        with self.assertRaises(ReplugError):
            runtime.load_all()

    def test_failed_load_keeps_previous_plugins_serving(self):
        self.plugins.write("alpha", version="1.0.0", init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.assertEqual(runtime.request("alpha", {"who": "值班"})["hits"], 1)

        self.plugins.write_source("alpha", "PLUGIN = {}\n")
        with self.assertRaises(ReplugError):
            runtime.load_all()
        self.assertEqual(runtime.plugin_names(), ["alpha"])
        self.assertEqual(runtime.version_of("alpha"), "1.0.0")
        self.assertEqual(runtime.state_of("alpha"), {"hits": 1})
        self.assertEqual(runtime.request("alpha", {"who": "值班"})["hits"], 2)

    def test_load_all_again_picks_up_file_changes_and_resets_state(self):
        self.plugins.write("alpha", version="1.0.0", init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        runtime.request("alpha", {"who": "值班"})
        self.plugins.write("alpha", version="1.1.0", init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        runtime.load_all()
        self.assertEqual(runtime.version_of("alpha"), "1.1.0")
        self.assertEqual(runtime.state_of("alpha"), {"hits": 0})


class RequestTest(support.RuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.plugins.write("alpha", version="1.0.0", init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        self.runtime = PluginRuntime(self.plugins.path)
        self.runtime.load_all()

    def test_request_result_and_live_state(self):
        first = self.runtime.request("alpha", {"who": "运维"})
        self.assertEqual(first, {"version": "1.0.0", "hits": 1, "who": "运维"})
        self.assertEqual(self.runtime.state_of("alpha"), {"hits": 1})
        self.assertEqual(self.runtime.request("alpha", {"who": "运维"})["hits"], 2)
        self.assertEqual(self.runtime.manifest_of("alpha").name, "alpha")

    def test_unknown_plugin_raises_not_found(self):
        for call in (lambda: self.runtime.request("ghost", {}),
                     lambda: self.runtime.state_of("ghost"),
                     lambda: self.runtime.version_of("ghost"),
                     lambda: self.runtime.manifest_of("ghost")):
            with self.assertRaises(PluginNotFound):
                call()

    def test_handler_error_wraps_and_runtime_keeps_serving(self):
        self.plugins.write_source("alpha", support.plugin_source(
            "alpha", "2.0.0",
            'if request.get("boom"):\n    raise ValueError("坏了")\nreturn "ok"'))
        self.runtime.load_all()
        with self.assertRaises(PluginError) as caught:
            self.runtime.request("alpha", {"boom": True})
        self.assertIn("alpha", str(caught.exception))
        self.assertEqual(self.runtime.request("alpha", {}), "ok")


class RestartReferenceTest(support.RuntimeTestCase):
    def test_restart_process_runs_calls_on_a_fresh_runtime(self):
        self.plugins.write("alpha", version="0.9.0", init_body="return {'n': 0}",
                           handle_body="state['n'] += 1\nreturn state['n']")
        calls = [("alpha", {}), ("alpha", {}), ("alpha", {})]
        self.assertEqual(restart_process(self.plugins.path, calls), [1, 2, 3])
        # 每次都是新宿主，状态从零开始，跟上面那个 3 无关
        self.assertEqual(restart_process(self.plugins.path, [("alpha", {})]), [1])

    def test_restart_process_sees_the_current_file_version(self):
        self.plugins.write_source("alpha", textwrap.dedent('''\
            PLUGIN = {"name": "alpha", "version": "1.0.0"}


            def handle(state, request):
                return "第一版"
            '''))
        self.assertEqual(restart_process(self.plugins.path, [("alpha", {})]),
                         ["第一版"])
        self.plugins.write_source("alpha", textwrap.dedent('''\
            PLUGIN = {"name": "alpha", "version": "2.0.0"}


            def handle(state, request):
                return "第二版"
            '''))
        self.assertEqual(restart_process(self.plugins.path, [("alpha", {})]),
                         ["第二版"])


if __name__ == "__main__":
    unittest.main()
