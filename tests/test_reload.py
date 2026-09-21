"""reload 热重载：状态迁移、失败作废、原子切换与规模性能。"""

import os
import sys
import textwrap
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from replug import (InitError, LoadError, ManifestError, MigrateError,  # noqa: E402
                    PluginError, PluginNotFound, PluginRuntime, ReplugError)
from replug.restart import restart_process  # noqa: E402

GREETER_BODY = '''\
state["hits"] += 1
return {"version": PLUGIN["version"], "hits": state["hits"],
        "who": request["who"]}
'''


class ReloadBasicTest(support.RuntimeTestCase):
    def test_reload_picks_up_new_version_and_code(self):
        self.plugins.write("alpha", version="1.0.0", init_body="return {}",
                           handle_body="return '旧版:' + request")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("alpha", version="2.0.0",
                           handle_body="return '新版:' + request")
        runtime.reload("alpha")
        self.assertEqual(runtime.version_of("alpha"), "2.0.0")
        self.assertEqual(runtime.request("alpha", "来了"), "新版:来了")

    def test_reload_without_migrate_carries_state_and_skips_init(self):
        self.plugins.write("alpha", version="1.0.0",
                           init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        runtime.request("alpha", {"who": "值班"})
        # 新版本即便定义了 init，reload 也不调它：旧状态照带
        self.plugins.write("alpha", version="2.0.0",
                           init_body="raise RuntimeError('init 不该被调用')",
                           handle_body=GREETER_BODY)
        runtime.reload("alpha")
        self.assertEqual(runtime.state_of("alpha"), {"hits": 1})
        self.assertEqual(
            runtime.request("alpha", {"who": "值班"})["hits"], 2)

    def test_reload_with_migrate_builds_new_state_from_old(self):
        self.plugins.write("alpha", version="1.0.0",
                           init_body="return {'hits': 5}",
                           handle_body="return state")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write_source("alpha", textwrap.dedent('''\
            PLUGIN = {"name": "alpha", "version": "2.0.0"}


            def migrate(old_state):
                old_state["hits"] += 10
                old_state["lang"] = "zh"
                return old_state


            def handle(state, request):
                return state
            '''))
        runtime.reload("alpha")
        self.assertEqual(runtime.state_of("alpha"),
                         {"hits": 15, "lang": "zh"})

    def test_reload_of_never_loaded_plugin_raises_not_found(self):
        runtime = PluginRuntime(self.plugins.path)
        with self.assertRaises(PluginNotFound):
            runtime.reload("ghost")


class ReloadFailureTest(support.RuntimeTestCase):
    def _serving_runtime(self):
        self.plugins.write("alpha", version="1.0.0",
                           init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        runtime.request("alpha", {"who": "值班"})
        return runtime

    def test_bad_import_voids_reload_and_old_version_serves(self):
        runtime = self._serving_runtime()
        self.plugins.write_source("alpha", "def handle(state, request)\n")
        with self.assertRaises(LoadError):
            runtime.reload("alpha")
        self.assertEqual(runtime.version_of("alpha"), "1.0.0")
        self.assertEqual(
            runtime.request("alpha", {"who": "值班"})["hits"], 2)
        self.assertEqual(runtime.state_of("alpha"), {"hits": 2})

    def test_missing_file_voids_reload(self):
        runtime = self._serving_runtime()
        os.remove(os.path.join(self.plugins.path, "alpha.py"))
        with self.assertRaises(ReplugError):
            runtime.reload("alpha")
        self.assertEqual(runtime.version_of("alpha"), "1.0.0")

    def test_bad_manifest_voids_reload(self):
        runtime = self._serving_runtime()
        self.plugins.write_source("alpha", "PLUGIN = {}\n")
        with self.assertRaises(ReplugError):
            runtime.reload("alpha")
        self.assertEqual(runtime.version_of("alpha"), "1.0.0")

    def test_missing_handle_voids_reload(self):
        runtime = self._serving_runtime()
        self.plugins.write_source(
            "alpha", 'PLUGIN = {"name": "alpha", "version": "2.0.0"}\n')
        with self.assertRaises(ReplugError):
            runtime.reload("alpha")
        self.assertEqual(runtime.version_of("alpha"), "1.0.0")

    def test_failing_migrate_voids_reload_and_keeps_state_intact(self):
        runtime = self._serving_runtime()
        self.plugins.write_source("alpha", textwrap.dedent('''\
            PLUGIN = {"name": "alpha", "version": "2.0.0"}


            def migrate(old_state):
                old_state["hits"] = 999
                old_state["tampered"] = True
                raise RuntimeError("迁移炸了")


            def handle(state, request):
                return state
            '''))
        before = dict(runtime.state_of("alpha"))
        with self.assertRaises(MigrateError) as caught:
            runtime.reload("alpha")
        self.assertIn("alpha", str(caught.exception))
        self.assertIsInstance(caught.exception, InitError)
        self.assertIsInstance(caught.exception, ReplugError)
        self.assertEqual(runtime.state_of("alpha"), before)
        self.assertNotIn("tampered", runtime.state_of("alpha"))
        self.assertEqual(runtime.version_of("alpha"), "1.0.0")
        self.assertEqual(
            runtime.request("alpha", {"who": "值班"})["hits"], 2)

    def test_failed_reload_is_retryable_until_good_version(self):
        runtime = self._serving_runtime()
        self.plugins.write_source("alpha", "def handle(state, request)\n")
        with self.assertRaises(LoadError):
            runtime.reload("alpha")
        self.plugins.write("alpha", version="1.1.0",
                           init_body="return {'hits': 0}",
                           handle_body=GREETER_BODY)
        runtime.reload("alpha")
        self.assertEqual(runtime.version_of("alpha"), "1.1.0")
        self.assertEqual(runtime.state_of("alpha"), {"hits": 1})


MIGRATE_SOURCE = '''\
PLUGIN = {"name": "alpha", "version": "2.0.0"}


def migrate(old_state):
    if not old_state.get("v2"):
        old_state["hits"] += 10
    old_state["v2"] = True
    return old_state


def handle(state, request):
    return state
'''


class MigrateIdempotenceTest(support.RuntimeTestCase):
    def test_migrating_repeatedly_never_double_applies(self):
        self.plugins.write("alpha", version="1.0.0",
                           init_body="return {'hits': 5, 'v2': False}",
                           handle_body="return state")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write_source("alpha", MIGRATE_SOURCE)
        for _ in range(5):
            runtime.reload("alpha")
            self.assertEqual(runtime.state_of("alpha"),
                             {"hits": 15, "v2": True})


class ReloadDependenciesTest(support.RuntimeTestCase):
    def test_reload_pulls_in_newly_required_missing_plugins(self):
        self.plugins.write("a", version="1.0.0",
                           handle_body="return PLUGIN['version']")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("b", version="1.0.0",
                           handle_body="return 'b:' + PLUGIN['version']")
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["b"]',
                           handle_body="return PLUGIN['version']")
        runtime.reload("a")
        self.assertEqual(runtime.plugin_names(), ["a", "b"])
        self.assertEqual(runtime.version_of("a"), "2.0.0")
        self.assertEqual(runtime.request("b", {}), "b:1.0.0")
        self.assertEqual(runtime.consistency_report(),
                         {"a": [], "b": []})

    def test_newly_required_plugin_missing_on_disk_voids_reload(self):
        self.plugins.write("a", version="1.0.0",
                           handle_body="return 'old'")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["ghost"]',
                           handle_body="return 'new'")
        with self.assertRaises(ReplugError):
            runtime.reload("a")
        self.assertEqual(runtime.version_of("a"), "1.0.0")
        self.assertEqual(runtime.request("a", {}), "old")
        self.assertEqual(runtime.plugin_names(), ["a"])

    def test_new_dependency_cycle_voids_reload(self):
        self.plugins.write("a", version="1.0.0",
                           handle_body="return 'old'")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("b", version="1.0.0",
                           manifest_extra='"requires": ["a"]',
                           handle_body="return 'b'")
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["b"]',
                           handle_body="return 'new'")
        with self.assertRaises(ManifestError):
            runtime.reload("a")
        self.assertEqual(runtime.version_of("a"), "1.0.0")


class RestartParityTest(support.RuntimeTestCase):
    def test_after_reload_responses_match_full_restart(self):
        self.plugins.write("c", version="1.0.0",
                           handle_body="return 'c-' + PLUGIN['version']")
        self.plugins.write("b", manifest_extra='"requires": ["c"]',
                           handle_body="return 'b-' + PLUGIN['version']")
        self.plugins.write("a", manifest_extra='"requires": ["b"]',
                           handle_body="return 'a-' + PLUGIN['version']")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        self.plugins.write("c", version="2.0.0",
                           handle_body="return 'c-' + PLUGIN['version']")
        runtime.reload("c")
        self.plugins.write("b", version="2.0.0",
                           manifest_extra='"requires": ["c"]',
                           handle_body="return 'b-' + PLUGIN['version']")
        runtime.reload("b")
        self.plugins.write("a", version="2.0.0",
                           manifest_extra='"requires": ["b"]',
                           handle_body="return 'a-' + PLUGIN['version']")
        runtime.reload("a")
        calls = [("a", {}), ("b", {}), ("c", {}), ("a", {})]
        self.assertEqual(
            [runtime.request(name, req) for name, req in calls],
            restart_process(self.plugins.path, calls))


COHERENCE_SOURCE = '''\
PLUGIN = {"name": "alpha", "version": "%s"}


def init(ctx):
    return {"count": 0, "schema": 1}


def migrate(old_state):
    old_state["schema"] = %d
    return old_state


def handle(state, request):
    state["count"] += 1
    return (PLUGIN["version"], state["schema"], state["count"])
'''

BROKEN_SOURCE = '''\
def migrate(old_state):
    raise RuntimeError("坏迁移")


def handle(state, request):
    return state
'''


class AtomicSwitchTest(support.RuntimeTestCase):
    def test_in_flight_request_finishes_on_old_version(self):
        entered = threading.Event()
        release = threading.Event()
        self.plugins.write_source("alpha", textwrap.dedent('''\
            PLUGIN = {"name": "alpha", "version": "1.0.0"}


            def handle(state, request):
                request["entered"].set()
                request["release"].wait(5)
                return ("1.0.0", PLUGIN["version"])
            '''))
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        result = []

        def worker():
            result.append(runtime.request(
                "alpha", {"entered": entered, "release": release}))

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(entered.wait(5))
        self.plugins.write("alpha", version="2.0.0",
                           handle_body="return ('2.0.0', PLUGIN['version'])")
        runtime.reload("alpha")
        release.set()
        thread.join(5)
        # 在途请求用的是进门前拿到的旧模块，不许半道变成新版本
        self.assertEqual(result, [("1.0.0", "1.0.0")])
        self.assertEqual(runtime.request("alpha", None),
                         ("2.0.0", "2.0.0"))

    def test_concurrent_requests_never_mix_versions(self):
        self.plugins.write_source(
            "alpha", COHERENCE_SOURCE % ("1.0.0", 2))
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        stop = threading.Event()
        errors = []

        def requester():
            while not stop.is_set():
                try:
                    version, schema, _ = runtime.request("alpha", {})
                except PluginError as exc:
                    errors.append(exc)
                    continue
                expected_schema = 1 if version == "1.0.0" else 2
                if schema != expected_schema:
                    errors.append(AssertionError(
                        "版本与结构混用: %r %r" % (version, schema)))

        workers = [threading.Thread(target=requester) for _ in range(8)]
        for worker in workers:
            worker.start()

        def reloader():
            for round_index in range(30):
                if round_index % 3 == 2:
                    # 每三轮夹一次必然作废的坏版本
                    self.plugins.write_source("alpha", BROKEN_SOURCE)
                    try:
                        runtime.reload("alpha")
                    except ReplugError:
                        pass
                    continue
                if round_index % 2 == 0:
                    self.plugins.write_source(
                        "alpha", COHERENCE_SOURCE % ("2.0.0", 2))
                else:
                    self.plugins.write_source(
                        "alpha", COHERENCE_SOURCE % ("1.0.0", 1))
                try:
                    runtime.reload("alpha")
                except ReplugError as exc:
                    errors.append(exc)

        reload_thread = threading.Thread(target=reloader)
        reload_thread.start()
        reload_thread.join(30)
        stop.set()
        for worker in workers:
            worker.join(5)
        self.assertEqual(errors, [])


class ReloadScaleTest(support.RuntimeTestCase):
    def _build_chain(self, size):
        # tip -> p1 -> p2 ... 一条链，init 做一点实在的活
        for index in range(size - 1, 0, -1):
            self.plugins.write(
                "p%d" % index,
                manifest_extra='"requires": ["p%d"]' % (index + 1),
                init_body="return {'n': sum(range(30))}",
                handle_body="return state['n']")
        self.plugins.write(
            "p%d" % size,
            init_body="return {'n': sum(range(30))}",
            handle_body="return state['n']")
        runtime = PluginRuntime(self.plugins.path)
        runtime.load_all()
        return runtime

    def _reload_time(self, runtime, size, rounds=7):
        # 反复改 tip 的版本号触发真实重读；坏版本作废也要算进来
        samples = []
        for round_index in range(rounds):
            if round_index == 0:
                continue  # 预热，不计入
            self.plugins.write(
                "p1", version="1.0.%d" % round_index,
                manifest_extra='"requires": ["p2"]',
                init_body="return {'n': sum(range(30))}",
                handle_body="return state['n']")
            start = time.perf_counter()
            runtime.reload("p1")
            samples.append(time.perf_counter() - start)
        return min(samples)

    def test_sixty_plugins_reload_not_three_times_slower(self):
        small = self._build_chain(6)
        small_time = self._reload_time(small, 6)

        big_dir = support.PluginDir()
        self.addCleanup(big_dir.close)
        self.plugins = big_dir
        big = self._build_chain(60)
        big_time = self._reload_time(big, 60)

        # reload 只动一个插件，开销不该随插件总数线性上涨
        self.assertLess(
            big_time, small_time * 3,
            "60 插件 %.4fs 比 6 插件 %.4fs 慢了三倍以上"
            % (big_time, small_time))


if __name__ == "__main__":
    unittest.main()
