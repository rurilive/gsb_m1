"""unregister 与错误隔离的行为契约测试。"""

import unittest

from pluginhost import Diagnostic, Plugin, PluginHost


class Recorder(Plugin):
    """记录调用痕迹，不改写消息。"""

    name = "rec"
    priority = 0

    def __init__(self, log):
        self.log = log

    def on_message(self, message):
        self.log.append((self.name, message))
        return None


class Appender(Plugin):
    """给消息加后缀，用于验证链式传递。"""

    name = "app"
    priority = 10

    def on_message(self, message):
        return message + "+app"


class Boom(Plugin):
    """on_message 必抛错的插件。"""

    name = "boom"
    priority = 5

    def __init__(self):
        self.calls = 0

    def on_message(self, message):
        self.calls += 1
        raise RuntimeError("boom on %s" % message)


class ErrorWatcher(Plugin):
    """记录收到的 on_error 诊断。"""

    name = "watcher"
    priority = 90

    def __init__(self):
        self.diags = []

    def on_error(self, diag):
        self.diags.append(diag)


class TestUnregister(unittest.TestCase):
    def test_unregister_removes_from_chain(self):
        host = PluginHost()
        log = []
        rec = Recorder(log)
        app = Appender()
        host.register(rec)
        host.register(app)
        host.unregister(rec)
        self.assertEqual(host.plugins, [app])
        self.assertNotIn(rec, host)
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x+app")
        self.assertEqual(log, [])  # 注销后钩子不再被调用

    def test_unregister_is_idempotent(self):
        host = PluginHost()
        app = Appender()
        host.register(app)
        host.unregister(app)
        host.unregister(app)  # 重复注销：静默
        host.unregister(Recorder([]))  # 从未注册：静默
        host.unregister(object())  # 非插件对象：静默
        self.assertEqual(host.plugins, [])

    def test_unregister_makes_no_callbacks(self):
        host = PluginHost()
        watcher = ErrorWatcher()
        app = Appender()
        host.register(watcher)
        host.register(app)
        host.unregister(app)
        self.assertEqual(watcher.diags, [])
        self.assertEqual(host.diagnostics, [])

    def test_reregister_lands_at_end_of_same_priority(self):
        host = PluginHost()

        class First(Plugin):
            name = "first"
            priority = 10

        class Second(Plugin):
            name = "second"
            priority = 10

        first, second = First(), Second()
        host.register(first)
        host.register(second)
        host.unregister(first)
        host.register(first)
        # 重新注册排在同 priority 的末尾，而不是回到原位
        self.assertEqual(host.plugins, [second, first])


class TestErrorIsolation(unittest.TestCase):
    def test_failure_skips_only_failing_plugin(self):
        host = PluginHost()
        log = []
        host.register(Recorder(log))
        host.register(Boom())
        host.register(Appender())
        out = host.dispatch("on_message", "x")
        # boom 抛错前的 payload 原样传给下游，dispatch 正常返回
        self.assertEqual(out, "x+app")
        self.assertEqual(log, [("rec", "x")])

    def test_diagnostic_records_plugin_hook_and_error(self):
        host = PluginHost()
        boom = Boom()
        host.register(boom)
        host.dispatch("on_message", "x")
        self.assertEqual(len(host.diagnostics), 1)
        diag = host.diagnostics[0]
        self.assertIsInstance(diag, Diagnostic)
        self.assertEqual(diag.plugin, "boom")
        self.assertEqual(diag.hook, "on_message")
        self.assertIsInstance(diag.error, RuntimeError)
        self.assertEqual(str(diag.error), "boom on x")

    def test_diagnostics_append_in_occurrence_order(self):
        host = PluginHost()

        class Boom2(Boom):
            name = "boom2"
            priority = 6

        host.register(Boom())
        host.register(Boom2())
        host.dispatch("on_message", "x")
        host.dispatch("on_message", "y")
        self.assertEqual(
            [(d.plugin, d.hook) for d in host.diagnostics],
            [("boom", "on_message"), ("boom2", "on_message"),
             ("boom", "on_message"), ("boom2", "on_message")])

    def test_error_event_fans_out_by_priority(self):
        host = PluginHost()
        calls = []

        class W(ErrorWatcher):
            def __init__(self, name, priority):
                self.name = name
                self.priority = priority
                self.diags = []

            def on_error(self, diag):
                calls.append(self.name)
                super().on_error(diag)

        late, early = W("late", 90), W("early", 1)
        host.register(late)
        host.register(Boom())
        host.register(early)
        host.dispatch("on_message", "x")
        # 所有在册插件都按 priority 收到 on_error
        self.assertEqual(calls, ["early", "late"])
        self.assertIs(early.diags[0], host.diagnostics[0])

    def test_on_error_failure_only_appends_diagnostics(self):
        host = PluginHost()

        class BadWatcher(Plugin):
            name = "bad-watcher"
            priority = 80

            def on_error(self, diag):
                raise ValueError("watcher broke")

        watcher = ErrorWatcher()
        host.register(BadWatcher())
        host.register(watcher)
        host.register(Boom())
        host.dispatch("on_message", "x")
        # 不二次触发：watcher 只收到最初那一条
        self.assertEqual(len(watcher.diags), 1)
        self.assertEqual(
            [(d.plugin, d.hook) for d in host.diagnostics],
            [("boom", "on_message"), ("bad-watcher", "on_error")])
        self.assertIsInstance(host.diagnostics[1].error, ValueError)


class TestRoundBoundary(unittest.TestCase):
    def test_unregister_during_dispatch_takes_effect_next_round(self):
        host = PluginHost()
        log = []
        rec = Recorder(log)
        app = Appender()

        class Unregisterer(Plugin):
            name = "unreg"
            priority = 5
            done = False

            def on_message(self, message):
                if not self.done:
                    host.unregister(app)
                    self.done = True
                return message + "+unreg"

        host.register(rec)
        host.register(Unregisterer())
        host.register(app)
        out = host.dispatch("on_message", "x")
        # 本轮仍按开头快照执行：app 照常参与
        self.assertEqual(out, "x+unreg+app")
        # 下一轮起 app 不在链上
        self.assertEqual(host.dispatch("on_message", "y"), "y+unreg")
        self.assertEqual([p.name for p in host.plugins], ["rec", "unreg"])

    def test_self_unregister_during_dispatch(self):
        host = PluginHost()
        log = []

        class Suicide(Plugin):
            name = "suicide"
            priority = 5

            def on_message(self, message):
                host.unregister(self)
                log.append(message)
                return None

        host.register(Suicide())
        host.register(Appender())
        host.dispatch("on_message", "x")
        host.dispatch("on_message", "y")
        self.assertEqual(log, ["x"])  # 第二轮起不再被调用

    def test_register_unregister_inside_on_error_is_safe(self):
        host = PluginHost()
        log = []

        class Late(Plugin):
            name = "late"
            priority = 99

            def on_error(self, diag):
                log.append("late")

        watcher = ErrorWatcher()

        class Meddler(Plugin):
            name = "meddler"
            priority = 50
            done = False

            def on_error(self, diag):
                log.append("meddler")
                if not self.done:
                    host.register(Late())  # 本轮 on_error 链不应出现 late
                    host.unregister(watcher)  # 本轮 watcher 仍应被调到
                    self.done = True

        host.register(watcher)
        host.register(Meddler())
        host.register(Boom())
        host.dispatch("on_message", "x")
        # 快照语义：meddler、watcher 各一次，late 本轮不参与
        self.assertEqual(log, ["meddler"])
        self.assertEqual(len(watcher.diags), 1)
        # 宿主状态没被改坏：late 已在册，watcher 已被摘除
        self.assertEqual(
            [p.name for p in host.plugins],
            ["boom", "meddler", "late"])
        # 下一轮 on_error 链包含 late，watcher 已注销不再收
        host.dispatch("on_message", "y")
        self.assertEqual(log, ["meddler", "meddler", "late"])
        self.assertEqual(len(watcher.diags), 1)

    def test_dispatch_result_unaffected_by_error_path_mutation(self):
        host = PluginHost()

        class Meddler(Plugin):
            name = "meddler"
            priority = 50

            def on_error(self, diag):
                host.unregister(host.plugin("app"))

        host.register(Boom())
        host.register(Meddler())
        host.register(Appender())
        out = host.dispatch("on_message", "x")
        # on_error 里注销 app 不影响本轮快照：app 仍执行
        self.assertEqual(out, "x+app")
        self.assertEqual(host.dispatch("on_message", "y"), "y")


if __name__ == "__main__":
    unittest.main()
