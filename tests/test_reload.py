"""热重载、依赖装载与一致性报告的用例。"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from replug import (InitError, LoadError, ManifestError, MigrateError,  # noqa: E402
                    PluginNotFound, PluginRuntime, ReplugError)
from replug.restart import restart_process  # noqa: E402

GREETER_V1 = support.plugin_source(
    "greeter", "1.0.0",
    'state["hits"] += 1\n'
    'return {"version": PLUGIN["version"], "hits": state["hits"]}',
    init_body="return {'hits': 0}")

GREETER_V2_WITH_MIGRATE = '''\
PLUGIN = {"name": "greeter", "version": "2.0.0"}


def migrate(old):
    old["hits"] = old.get("hits", 0)
    old["lang"] = "zh"
    return old


def handle(state, request):
    state["hits"] += 1
    return {"version": PLUGIN["version"], "hits": state["hits"],
            "lang": state.get("lang")}
'''

GREETER_V2_NO_MIGRATE = support.plugin_source(
    "greeter", "2.0.0",
    'state["hits"] += 1\n'
    'return {"version": PLUGIN["version"], "hits": state["hits"]}',
    init_body="raise AssertionError('reload 不该调 init')\nreturn {'hits': 0}")

GREETER_SYNTAX_ERROR = "def handle(state, request\n"


class ReloadBasicTest(support.RuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.plugins.write_source("greeter", GREETER_V1)
        self.runtime = PluginRuntime(self.plugins.path)
        self.runtime.load_all()
        self.runtime.request("greeter", {})
        self.runtime.request("greeter", {})

    def test_reload_with_migrate_keeps_and_upgrades_state(self):
        self.plugins.write_source("greeter", GREETER_V2_WITH_MIGRATE)
        version = self.runtime.reload("greeter")
        self.assertEqual(version, "2.0.0")
        self.assertEqual(self.runtime.version_of("greeter"), "2.0.0")
        self.assertEqual(self.runtime.state_of("greeter"),
                         {"hits": 2, "lang": "zh"})
        self.assertEqual(self.runtime.request("greeter", {}),
                         {"version": "2.0.0", "hits": 3, "lang": "zh"})

    def test_reload_without_migrate_carries_state_and_skips_init(self):
        self.plugins.write_source("greeter", GREETER_V2_NO_MIGRATE)
        self.runtime.reload("greeter")
        self.assertEqual(self.runtime.version_of("greeter"), "2.0.0")
        self.assertEqual(self.runtime.state_of("greeter"), {"hits": 2})
        self.assertEqual(self.runtime.request("greeter", {})["hits"], 3)

    def test_reload_does_not_touch_other_plugins(self):
        self.plugins.write("other", version="1.0.0", init_body="return {'n': 0}",
                           handle_body="state['n'] += 1\nreturn state['n']")
        self.runtime.load_all()
        self.plugins.write_source("greeter", GREETER_V2_WITH_MIGRATE)
        self.assertEqual(self.runtime.reload("greeter"), "2.0.0")
        self.assertEqual(self.runtime.plugin_names(), ["greeter", "other"])
        self.assertEqual(self.runtime.version_of("other"), "1.0.0")
        self.assertEqual(self.runtime.request("other", {}), 1)

    def test_failed_migrate_aborts_reload_old_state_untouched(self):
        state_before = self.runtime.state_of("greeter")
        bad = support.plugin_source(
            "greeter", "3.0.0", "return '不该出现'",
            init_body="return {}")
        bad = bad.replace(
            "def handle(state, request):",
            "def migrate(old):\n"
            "    old['hits'] = -999\n"
            "    raise RuntimeError('迁移炸了')\n\n\n"
            "def handle(state, request):")
        self.plugins.write_source("greeter", bad)
        with self.assertRaises(MigrateError) as caught:
            self.runtime.reload("greeter")
        self.assertIn("greeter", str(caught.exception))
        self.assertEqual(self.runtime.version_of("greeter"), "1.0.0")
        self.assertIs(self.runtime.state_of("greeter"), state_before)
        self.assertEqual(self.runtime.state_of("greeter"), {"hits": 2})
        self.assertEqual(self.runtime.request("greeter", {})["hits"], 3)
        self.assertEqual(
            sys.modules["_replug_plugin_greeter"].PLUGIN["version"], "1.0.0")

    def test_syntax_error_aborts_reload_old_version_keeps_serving(self):
        state_before = self.runtime.state_of("greeter")
        self.plugins.write_source("greeter", GREETER_SYNTAX_ERROR)
        with self.assertRaises(LoadError):
            self.runtime.reload("greeter")
        self.assertEqual(self.runtime.version_of("greeter"), "1.0.0")
        self.assertIs(self.runtime.state_of("greeter"), state_before)
        self.assertEqual(self.runtime.request("greeter", {})["hits"], 3)

    def test_manifest_error_aborts_reload(self):
        self.plugins.write_source(
            "greeter", 'PLUGIN = {"name": "impostor", "version": "9.0.0"}\n'
                       "def handle(state, request):\n    return 1\n")
        with self.assertRaises(ManifestError):
            self.runtime.reload("greeter")
        self.assertEqual(self.runtime.version_of("greeter"), "1.0.0")
        self.assertEqual(self.runtime.request("greeter", {})["hits"], 3)

    def test_reload_unknown_plugin_raises_not_found(self):
        with self.assertRaises(PluginNotFound):
            self.runtime.reload("ghost")

    def test_missing_file_aborts_reload(self):
        os.remove(os.path.join(self.plugins.path, "greeter.py"))
        with self.assertRaises(ReplugError):
            self.runtime.reload("greeter")
        self.assertEqual(self.runtime.version_of("greeter"), "1.0.0")
        self.assertEqual(self.runtime.request("greeter", {})["hits"], 3)

    def test_repeated_migration_of_same_state_is_idempotent(self):
        self.plugins.write_source("greeter", GREETER_V2_WITH_MIGRATE)
        hits = 2
        for expected in (3, 4, 5):
            self.runtime.reload("greeter")
            hits += 1
            self.assertEqual(self.runtime.state_of("greeter")["lang"], "zh")
            self.assertEqual(
                self.runtime.request("greeter", {})["hits"], expected)

    def test_failed_reload_then_success_recovers(self):
        self.plugins.write_source("greeter", GREETER_SYNTAX_ERROR)
        with self.assertRaises(LoadError):
            self.runtime.reload("greeter")
        self.plugins.write_source("greeter", GREETER_V2_WITH_MIGRATE)
        self.assertEqual(self.runtime.reload("greeter"), "2.0.0")
        self.assertEqual(self.runtime.request("greeter", {}),
                         {"version": "2.0.0", "hits": 3, "lang": "zh"})

    def test_plugin_without_init_migrates_from_none(self):
        self.plugins.write_source("plain",
                                  "PLUGIN = {'name': 'plain', 'version': '1.0.0'}\n"
                                  "def handle(state, request):\n    return state\n")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.assertIsNone(runtime.request("plain", {}))
        self.plugins.write_source(
            "plain",
            "PLUGIN = {'name': 'plain', 'version': '2.0.0'}\n\n\n"
            "def migrate(old):\n    return {'seen': old}\n\n\n"
            "def handle(state, request):\n    return state\n")
        runtime.reload("plain")
        self.assertEqual(runtime.request("plain", {}), {"seen": None})

    def test_migrate_receives_a_copy_not_the_live_state(self):
        self.plugins.write("sneaky", version="1.0.0",
                           init_body="return {'n': 1}",
                           handle_body="return state")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write_source(
            "sneaky",
            "PLUGIN = {'name': 'sneaky', 'version': '2.0.0'}\n"
            "ESCAPED = []\n\n\n"
            "def migrate(old):\n"
            "    ESCAPED.append(old)\n"
            "    raise RuntimeError('先放跑副本再说')\n\n\n"
            "def handle(state, request):\n    return state\n")
        with self.assertRaises(MigrateError):
            runtime.reload("sneaky")
        self.assertEqual(runtime.state_of("sneaky"), {"n": 1})
        self.assertEqual(
            sys.modules["_replug_plugin_sneaky"].PLUGIN["version"], "1.0.0")
        # 旧状态对象原样留任，后续请求照常累加
        self.assertEqual(runtime.request("sneaky", {}), {"n": 1})

    def test_migrate_copy_is_deep_and_disconnected_from_live_state(self):
        self.plugins.write_source(
            "nest", support.plugin_source(
                "nest", "1.0.0", "return state",
                init_body="return {'inner': {'n': 1}, 'escaped': None}"))
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write_source(
            "nest",
            "PLUGIN = {'name': 'nest', 'version': '2.0.0'}\n\n\n"
            "def migrate(old):\n"
            "    old['escaped'] = old['inner']\n"
            "    old['inner']['n'] = 999\n"
            "    raise RuntimeError('放跑深拷贝')\n\n\n"
            "def handle(state, request):\n    return state\n")
        with self.assertRaises(MigrateError):
            runtime.reload("nest")
        live = runtime.state_of("nest")
        self.assertEqual(live, {"inner": {"n": 1}, "escaped": None})


GREETER_REQUIRES_BASE = '''\
PLUGIN = {"name": "greeter", "version": "1.0.0", "requires": ["base"]}


def handle(state, request):
    return "greeter v1 over %s" % request
'''


class RequiresLoadingTest(support.RuntimeTestCase):
    def _write_base_greeter(self, base_version="1.0.0"):
        self.plugins.write(
            "base", version=base_version,
            init_body="import os\n"
                      "with open(os.path.join(ctx.plugin_dir, 'order.log'),"
                      " 'a') as f:\n"
                      "    f.write('base:%s\\n' % ctx.version)",
            handle_body="return request")
        self.plugins.write_source("greeter", GREETER_REQUIRES_BASE)

    def test_load_all_inits_dependencies_first(self):
        self._write_base_greeter()
        log = os.path.join(self.plugins.path, "order.log")
        runtime = PluginRuntime(self.plugins.path)
        self.assertEqual(runtime.load_all(), ["base", "greeter"])
        with open(log, encoding="utf-8") as stream:
            self.assertEqual(stream.read().splitlines(), ["base:1.0.0"])

    def test_transitive_requires_are_topo_ordered(self):
        self.plugins.write("root", version="1.0.0",
                           manifest_extra="'requires': ['mid']",
                           init_body="return {}", handle_body="return 'root'")
        self.plugins.write("mid", version="1.0.0",
                           manifest_extra="'requires': ['leaf']",
                           init_body="return {}", handle_body="return 'mid'")
        self.plugins.write("leaf", version="1.0.0",
                           init_body="return {}", handle_body="return 'leaf'")
        runtime = PluginRuntime(self.plugins.path)
        self.assertEqual(runtime.load_all(), ["leaf", "mid", "root"])
        self.assertEqual(runtime.request("root", {}), "root")

    def test_missing_requirement_fails_atomic_load(self):
        self.plugins.write_source("greeter", GREETER_REQUIRES_BASE)
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(ManifestError) as caught:
            runtime.load_all()
        self.assertIn("base", str(caught.exception))
        self.assertEqual(runtime.plugin_names(), [])

    def test_dependency_cycle_is_rejected(self):
        self.plugins.write("alpha", version="1.0.0",
                           manifest_extra="'requires': ['beta']",
                           init_body="return {}", handle_body="return 1")
        self.plugins.write("beta", version="1.0.0",
                           manifest_extra="'requires': ['alpha']",
                           init_body="return {}", handle_body="return 2")
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(ManifestError):
            runtime.load_all()
        self.assertEqual(runtime.plugin_names(), [])

    def test_bad_requires_manifest(self):
        for extra in ("'requires': 'base'", "'requires': ['']",
                      "'requires': ['base', 'base']",
                      "'requires': ['plain']"):
            self.plugins.write("plain", version="1.0.0",
                               manifest_extra=extra,
                               init_body="return {}", handle_body="return 1")
            with self.assertRaises(ManifestError):
                PluginRuntime(self.plugins.path).load_all()
            os.remove(os.path.join(self.plugins.path, "plain.py"))

    def test_reload_to_requirement_not_loaded_aborts(self):
        self.plugins.write("plain", version="1.0.0",
                           init_body="return {}", handle_body="return 1")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write_source(
            "plain",
            'PLUGIN = {"name": "plain", "version": "2.0.0",'
            ' "requires": ["ghost"]}\n'
            "def handle(state, request):\n    return 2\n")
        with self.assertRaises(ManifestError):
            runtime.reload("plain")
        self.assertEqual(runtime.version_of("plain"), "1.0.0")

    def test_reload_creating_cycle_aborts(self):
        self.plugins.write("alpha", version="1.0.0",
                           manifest_extra="'requires': ['beta']",
                           init_body="return {}", handle_body="return 1")
        self.plugins.write("beta", version="1.0.0",
                           init_body="return {}", handle_body="return 2")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("beta", version="2.0.0",
                           manifest_extra="'requires': ['alpha']",
                           init_body="return {}", handle_body="return 3")
        with self.assertRaises(ManifestError):
            runtime.reload("beta")
        self.assertEqual(runtime.version_of("beta"), "1.0.0")
        self.assertEqual(runtime.request("beta", {}), 2)

    def test_init_failure_in_load_all_leaves_previous_runtime_intact(self):
        self._write_base_greeter()
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("base", version="2.0.0",
                           init_body="raise RuntimeError('炸了')",
                           handle_body="return request")
        with self.assertRaises(InitError):
            runtime.load_all()
        self.assertEqual(runtime.version_of("base"), "1.0.0")
        self.assertEqual(runtime.version_of("greeter"), "1.0.0")


class ConsistencyReportTest(support.RuntimeTestCase):
    def _load_chain(self):
        self.plugins.write("base", version="1.0.0",
                           init_body="return {}", handle_body="return 1")
        self.plugins.write("mid", version="1.0.0",
                           manifest_extra="'requires': ['base']",
                           init_body="return {}", handle_body="return 2")
        self.plugins.write("top", version="1.0.0",
                           manifest_extra="'requires': ['mid']",
                           init_body="return {}", handle_body="return 3")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        return runtime

    def test_fresh_load_is_consistent(self):
        runtime = self._load_chain()
        self.assertEqual(runtime.consistency_report(), {})

    def test_reloading_dependency_marks_dependents_stale(self):
        runtime = self._load_chain()
        self.plugins.write("base", version="2.0.0",
                           init_body="return {}", handle_body="return 1")
        runtime.reload("base")
        self.assertEqual(runtime.consistency_report(),
                         {"mid": ["base"]})
        self.plugins.write("mid", version="2.0.0",
                           manifest_extra="'requires': ['base']",
                           init_body="return {}", handle_body="return 2")
        runtime.reload("mid")
        self.assertEqual(runtime.consistency_report(),
                         {"base": ["mid"], "top": ["mid"]})
        self.plugins.write("top", version="2.0.0",
                           manifest_extra="'requires': ['mid']",
                           init_body="return {}", handle_body="return 3")
        runtime.reload("top")
        self.assertEqual(runtime.consistency_report(),
                         {"base": ["mid"], "mid": ["top"]})

    def test_reloading_dependent_reports_its_dependency_as_stale(self):
        runtime = self._load_chain()
        self.plugins.write("top", version="2.0.0",
                           manifest_extra="'requires': ['mid']",
                           init_body="return {}", handle_body="return 3")
        runtime.reload("top")
        self.assertEqual(runtime.consistency_report(), {"mid": ["top"]})

    def test_independent_plugins_do_not_appear_in_report(self):
        runtime = self._load_chain()
        self.plugins.write("loner", version="1.0.0",
                           init_body="return {}", handle_body="return 9")
        runtime.load_all()
        self.plugins.write("loner", version="2.0.0",
                           init_body="return {}", handle_body="return 9")
        runtime.reload("loner")
        self.assertEqual(runtime.consistency_report(), {})


class RestartEquivalenceTest(support.RuntimeTestCase):
    def test_state_after_reload_matches_fresh_restart_with_migrate(self):
        greeter_v2 = '''\
PLUGIN = {"name": "greeter", "version": "2.0.0"}


def init(ctx):
    return {"hits": 5, "lang": "zh"}


def migrate(old):
    old["lang"] = "zh"
    return old


def handle(state, request):
    state["hits"] += 1
    return {"version": PLUGIN["version"], "hits": state["hits"]}
'''
        self.plugins.write("greeter", version="1.0.0",
                           init_body="return {'hits': 0}",
                           handle_body=(
                               'state["hits"] += 1\n'
                               'return {"version": PLUGIN["version"],'
                               ' "hits": state["hits"]}'))
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        for _ in range(5):
            runtime.request("greeter", {})
        self.plugins.write_source("greeter", greeter_v2)
        runtime.reload("greeter")
        calls = [("greeter", {}) for _ in range(3)]
        def run_calls(rt):
            return [rt.request(name, req) for name, req in calls]
        self.assertEqual(run_calls(runtime),
                         restart_process(self.plugins.path, calls))
        self.assertEqual([result["hits"] for result in run_calls(runtime)],
                         [9, 10, 11])

    def test_reload_with_dependencies_matches_restart(self):
        self.plugins.write("base", version="1.0.0",
                           handle_body="return PLUGIN['version'] + ':' + request")
        self.plugins.write("app", version="1.0.0",
                           manifest_extra="'requires': ['base']",
                           handle_body="return PLUGIN['version'] + ':' + request")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("app", version="2.0.0",
                           manifest_extra="'requires': ['base']",
                           handle_body="return PLUGIN['version'] + ':' + request")
        runtime.reload("app")
        calls = [("app", "x"), ("base", "y"), ("app", "z")]
        hot_results = [runtime.request(n, r) for n, r in calls]
        restart_results = restart_process(self.plugins.path, calls)
        self.assertEqual(hot_results, restart_results)


FLIP_PLUGIN = support.plugin_source(
    "flip", "1.0.0",
    "state['hits'] += 1\n"
    "return PLUGIN['version'], state['hits']",
    init_body="return {'hits': 0}")


def _flip_source(version):
    return support.plugin_source(
        "flip", version,
        "state['hits'] += 1\n"
        "return PLUGIN['version'], state['hits']",
        init_body="return {'hits': 0}")


class ConcurrencyTest(support.RuntimeTestCase):
    def test_random_reloads_never_mix_versions_or_break_requests(self):
        self.plugins.write_source("flip", FLIP_PLUGIN)
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        errors = []
        results = []
        results_lock = threading.Lock()
        stop = threading.Event()

        def worker():
            try:
                while not stop.is_set():
                    version, hits = runtime.request("flip", {})
                    with results_lock:
                        results.append((version, hits))
            except Exception as exc:  # pragma: no cover - 失败即用例挂
                errors.append(exc)

        versions = ["1.0.0", "2.0.0", "3.0.0", "4.0.0"]

        def reloader():
            import random

            rng = random.Random(1234)
            for _ in range(200):
                version = rng.choice(versions)
                self.plugins.write_source("flip", _flip_source(version))
                try:
                    runtime.reload("flip")
                except ReplugError:
                    pass

        workers = [threading.Thread(target=worker) for _ in range(8)]
        for thread in workers:
            thread.start()
        reload_thread = threading.Thread(target=reloader)
        reload_thread.start()
        reload_thread.join()
        stop.set()
        for thread in workers:
            thread.join()
        self.assertEqual(errors, [])
        self.assertTrue(results)
        # 每条响应的版本号必须是当时真实在跑的版本之一
        for version, _hits in results:
            self.assertIn(version, versions)
        # 状态计数必须严格连续，没有丢更新
        hits = [hits for _version, hits in results]
        self.assertEqual(sorted(hits), list(range(1, len(hits) + 1)))

    def test_inflight_request_runs_on_one_version_even_while_reloading(self):
        entered = threading.Event()
        release = threading.Event()
        self.plugins.write(
            "slow", version="1.0.0",
            init_body="return {}",
            handle_body=("import threading\n"
                         "entered.set()\n"
                         "release.wait(5)\n"
                         "return ('v1', PLUGIN['version'])"))
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        plugin_module = sys.modules["_replug_plugin_slow"]
        plugin_module.entered = entered
        plugin_module.release = release

        def handle():
            return runtime.request("slow", {})

        holder = {}
        request_thread = threading.Thread(
            target=lambda: holder.update({"result": handle()}))
        request_thread.start()
        self.assertTrue(entered.wait(5))
        self.plugins.write("slow", version="2.0.0",
                           init_body="return {}",
                           handle_body="return ('v2', PLUGIN['version'])")
        # 重载必须等在途请求结束：handle 还没放行时版本仍是旧版
        reloaded = threading.Event()

        def do_reload():
            runtime.reload("slow")
            reloaded.set()

        reload_thread = threading.Thread(target=do_reload)
        reload_thread.start()
        time.sleep(0.1)
        # handle 还没放行：重载只能在锁外等，不能抢先切换
        self.assertFalse(reloaded.is_set())
        self.assertEqual(runtime._plugins["slow"].manifest.version, "1.0.0")
        release.set()
        reload_thread.join(5)
        request_thread.join(5)
        self.assertTrue(reloaded.is_set())
        self.assertEqual(holder["result"], ("v1", "1.0.0"))
        self.assertEqual(runtime.request("slow", {}), ("v2", "2.0.0"))


class PerformanceTest(support.RuntimeTestCase):
    def test_reload_with_sixty_plugins_is_not_three_times_slower(self):
        self.plugins.write("target", version="1.0.0",
                           init_body="return {'hits': 0}",
                           handle_body="state['hits'] += 1\nreturn state['hits']")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()

        def timed_reload(times):
            start = time.perf_counter()
            for _ in range(times):
                runtime.reload("target")
            return time.perf_counter() - start

        small = sorted(timed_reload(15) for _ in range(5))[len(range(5)) // 2]
        for index in range(54):
            name = "extra%02d" % index
            self.plugins.write(name, version="1.0.0",
                               init_body="return {}",
                               handle_body="return request")
        runtime.load_all()
        big = sorted(timed_reload(15) for _ in range(5))[len(range(5)) // 2]
        self.assertLess(big, small * 3,
                        "60 插件重载 %.4fs，6 插件 %.4fs" % (big, small))


if __name__ == "__main__":
    unittest.main()
