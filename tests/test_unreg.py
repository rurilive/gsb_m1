"""unregister 与错误隔离的行为测试。"""

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

    def on_message(self, message):
        raise RuntimeError("boom on %r" % message)


class ErrorRecorder(Plugin):
    """记录 on_error 收到的 Diagnostic。"""

    name = "err-rec"
    priority = 0

    def __init__(self, log):
        self.log = log

    def on_error(self, diag):
        self.log.append((self.name, diag))


def make_host(*plugins):
    host = PluginHost()
    for p in plugins:
        host.register(p)
    return host


class TestUnregister(unittest.TestCase):
    def test_unregister_removes_from_chain(self):
        log = []
        rec, app = Recorder(log), Appender()
        host = make_host(rec, app)
        host.unregister(app)
        self.assertEqual(host.plugins, [rec])
        self.assertEqual(len(host), 1)
        self.assertNotIn(app, host)
        with self.assertRaises(KeyError):
            host.plugin("app")
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x")  # app 不再参与
        self.assertEqual(log, [("rec", "x")])

    def test_unregister_is_idempotent(self):
        host = make_host(Appender())
        host.unregister(Appender())  # 从未注册的实例：静默
        app = host.plugin("app")
        host.unregister(app)
        host.unregister(app)  # 重复注销：静默
        self.assertEqual(host.plugins, [])

    def test_unregister_triggers_no_callback(self):
        calls = []

        class Probe(Plugin):
            name = "probe"

            def __getattribute__(self, attr):
                if attr.startswith("on_"):
                    calls.append(attr)
                return object.__getattribute__(self, attr)

        host = PluginHost()
        probe = Probe()
        host.register(probe)
        calls.clear()
        host.unregister(probe)
        host.dispatch("on_message", "x")
        self.assertEqual(calls, [])  # 注销本身与之后的 dispatch 都不碰它

    def test_unregister_mid_round_takes_effect_next_round(self):
        log = []
        host = PluginHost()
        late = Recorder(log)
        late.name, late.priority = "late", 10

        class Kicker(Plugin):
            name = "kicker"
            priority = 0
            kicked = False

            def on_message(self, message):
                if not self.kicked:
                    host.unregister(late)  # dispatch 途中注销
                    self.kicked = True
                return None

        host.register(Kicker())
        host.register(late)
        host.dispatch("on_message", "x")
        # 本轮用开始时的快照：late 仍被调用
        self.assertEqual(log, [("late", "x")])
        self.assertEqual(host.plugins, [host.plugin("kicker")])
        host.dispatch("on_message", "y")
        self.assertEqual(log, [("late", "x")])  # 下一轮起不再调用

    def test_reregister_lands_at_end_of_same_priority(self):
        host = PluginHost()

        def named(name):
            p = Appender()
            p.name, p.priority = name, 10
            return p

        x, y, z = named("x"), named("y"), named("z")
        host.register(x)
        host.register(y)
        host.register(z)
        host.unregister(y)
        host.register(y)  # 重新注册：排到同 priority 末尾，不回到原位
        self.assertEqual([p.name for p in host.plugins], ["x", "z", "y"])

    def test_same_priority_order_stable_without_unregister(self):
        host = PluginHost()
        a, b = Appender(), Recorder([])
        a.priority = b.priority = 10
        b.name = "rec2"
        host.register(a)
        host.register(b)
        host.dispatch("on_message", "x")  # 一轮 dispatch 不打乱顺序
        self.assertEqual(host.plugins, [a, b])


class TestErrorIsolation(unittest.TestCase):
    def test_failing_plugin_skipped_others_continue(self):
        log = []
        host = make_host(Recorder(log), Boom(), Appender())
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x+app")  # dispatch 不再被炸断
        self.assertEqual(log, [("rec", "x")])

    def test_payload_before_error_flows_downstream(self):
        seen = []

        class First(Plugin):
            name = "first"
            priority = 0

            def on_message(self, message):
                return message + "+first"

        class Last(Plugin):
            name = "last"
            priority = 10

            def on_message(self, message):
                seen.append(message)
                return None

        host = make_host(First(), Boom(), Last())
        host.dispatch("on_message", "x")
        # boom 抛错前的链上值继续往下游传
        self.assertEqual(seen, ["x+first"])

    def test_diagnostics_recorded_in_order(self):
        host = PluginHost()
        b1, b2 = Boom(), Boom()
        b1.name, b1.priority = "b1", 0
        b2.name, b2.priority = "b2", 10
        host.register(b1)
        host.register(b2)
        host.dispatch("on_message", "x")
        self.assertEqual(len(host.diagnostics), 2)
        self.assertEqual([d.plugin for d in host.diagnostics], ["b1", "b2"])
        for d in host.diagnostics:
            self.assertIsInstance(d, Diagnostic)
            self.assertEqual(d.hook, "on_message")
            self.assertIsInstance(d.error, RuntimeError)
        self.assertIn("x", str(host.diagnostics[0].error))

    def test_error_event_fans_out_by_priority(self):
        log = []
        host = PluginHost()
        for name, prio in [("c", 20), ("a", 0), ("b", 10)]:
            p = ErrorRecorder(log)
            p.name, p.priority = name, prio
            host.register(p)

        class BoomWithHandler(Boom):
            name = "boom"
            priority = 5

            def on_error(self, diag):
                log.append(("boom", diag))

        host.register(BoomWithHandler())  # 出错插件自身在册，也收 on_error
        host.dispatch("on_message", "x")
        self.assertEqual([t[0] for t in log], ["a", "boom", "b", "c"])
        diag = log[0][1]
        self.assertEqual((diag.plugin, diag.hook), ("boom", "on_message"))

    def test_on_error_error_recorded_without_retrigger(self):
        log = []

        class BadHandler(Plugin):
            name = "bad-handler"
            priority = 0

            def on_error(self, diag):
                log.append(diag)
                raise ValueError("handler broken")

        host = make_host(BadHandler(), Boom(), ErrorRecorder(log))
        host.dispatch("on_message", "x")
        # bad-handler 的 on_error 抛错：只记 diagnostics，不二次触发
        self.assertEqual(len(log), 2)  # 两个插件各收到一次，没有重复触发
        self.assertEqual(len(host.diagnostics), 2)
        handler_diag = host.diagnostics[1]
        self.assertEqual(handler_diag.plugin, "bad-handler")
        self.assertEqual(handler_diag.hook, "on_error")
        self.assertIsInstance(handler_diag.error, ValueError)

    def test_on_error_may_register_and_unregister_safely(self):
        host = make_host(Boom(), Appender())
        app = host.plugin("app")

        class Janitor(Plugin):
            name = "janitor"
            priority = 99
            fired = 0

            def on_error(self, diag):
                self.fired += 1
                if self.fired == 1:
                    host.unregister(app)  # error 事件里注销
                    extra = Recorder([])
                    extra.name = "extra"
                    host.register(extra)  # error 事件里注册

        host.register(Janitor())
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x+app")  # 本轮快照不受影响
        self.assertEqual(host.diagnostics[0].plugin, "boom")
        # extra priority 0，按序排到最前
        self.assertEqual([p.name for p in host.plugins], ["extra", "boom", "janitor"])
        out = host.dispatch("on_message", "y")
        self.assertEqual(out, "y")  # 下一轮 app 已摘除、extra 不改写
        self.assertEqual(len(host.diagnostics), 2)  # 每轮各记一条，不漏不重

    def test_error_inside_error_handler_dispatch_isolated(self):
        # 直接 dispatch("on_error", ...) 时抛错也只记 diagnostics
        class BadHandler(Plugin):
            name = "bad-handler"

            def on_error(self, diag):
                raise ValueError("nope")

        host = make_host(BadHandler())
        out = host.dispatch("on_error", "payload")
        self.assertEqual(out, "payload")
        self.assertEqual(len(host.diagnostics), 1)
        self.assertEqual(host.diagnostics[0].hook, "on_error")

    def test_chain_recovers_next_round(self):
        log = []
        host = make_host(Recorder(log), Boom(), Appender())
        host.dispatch("on_message", "x")
        out = host.dispatch("on_message", "y")
        self.assertEqual(out, "y+app")
        self.assertEqual(log, [("rec", "x"), ("rec", "y")])
        self.assertEqual(len(host.diagnostics), 2)


if __name__ == "__main__":
    unittest.main()
