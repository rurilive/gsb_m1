"""PluginHost 现有行为的锁定测试。"""

import unittest

from pluginhost import Plugin, PluginHost
from pluginhost.plugins import AuditTrail, CollapseRepeats, FooterSigner, KeywordMask


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


class Upper(Plugin):
    """转大写，priority 相同时验证注册先后。"""

    name = "upper"
    priority = 10

    def on_message(self, message):
        return message.upper()


class NoHooks(Plugin):
    """没有任何业务钩子的插件，dispatch 时应被跳过。"""

    name = "quiet"
    priority = 1


class BrokenRegistered(Plugin):
    """on_registered 抛错的插件。"""

    name = "broken-reg"

    def on_registered(self, host):
        raise RuntimeError("registration failed")


class TestRegister(unittest.TestCase):
    def test_priority_order(self):
        host = PluginHost()
        late = Appender()
        early = Recorder([])
        early.priority = 5
        host.register(late)
        host.register(early)
        self.assertEqual(host.plugins, [early, late])

    def test_same_priority_keeps_registration_order(self):
        host = PluginHost()
        first = Appender()
        second = Upper()
        host.register(first)
        host.register(second)
        self.assertEqual(host.plugins, [first, second])

    def test_plugins_returns_copy(self):
        host = PluginHost()
        p = Appender()
        host.register(p)
        host.plugins.append("junk")
        self.assertEqual(host.plugins, [p])

    def test_requires_plugin_instance(self):
        host = PluginHost()
        with self.assertRaises(TypeError):
            host.register(object())

    def test_empty_name_rejected(self):
        host = PluginHost()
        p = Appender()
        p.name = ""
        with self.assertRaises(ValueError):
            host.register(p)

    def test_duplicate_name_rejected(self):
        host = PluginHost()
        host.register(Appender())
        with self.assertRaises(ValueError):
            host.register(Appender())

    def test_on_registered_called_with_host(self):
        seen = []

        class Probe(Plugin):
            name = "probe"

            def on_registered(self, host):
                seen.append(host)

        host = PluginHost()
        p = Probe()
        host.register(p)
        self.assertEqual(seen, [host])

    def test_on_registered_error_rolls_back(self):
        host = PluginHost()
        with self.assertRaises(RuntimeError):
            host.register(BrokenRegistered())
        self.assertEqual(host.plugins, [])
        # 回滚后同名可以重新注册
        host.register(Appender())
        self.assertEqual([p.name for p in host.plugins], ["app"])

    def test_contains_by_identity(self):
        host = PluginHost()
        p = Appender()
        host.register(p)
        self.assertIn(p, host)
        q = Appender()
        self.assertNotIn(q, host)

    def test_len_and_lookup_by_name(self):
        host = PluginHost()
        app = Appender()
        host.register(app)
        self.assertEqual(len(host), 1)
        self.assertIs(host.plugin("app"), app)
        with self.assertRaises(KeyError):
            host.plugin("nope")


class TestDispatch(unittest.TestCase):
    def test_chain_through_example_plugins(self):
        host = PluginHost()
        host.register(KeywordMask(["密码"]))
        host.register(FooterSigner(" -- 已签名"))
        out = host.dispatch("on_message", "我的密码是 123456")
        self.assertEqual(out, "<masked> -- 已签名")
        out = host.dispatch("on_message", "正常消息")
        self.assertEqual(out, "正常消息 -- 已签名")

    def test_none_return_passes_payload_through(self):
        host = PluginHost()
        log = []
        host.register(Recorder(log))
        host.register(Appender())
        out = host.dispatch("on_message", "hello")
        self.assertEqual(out, "hello+app")
        self.assertEqual(log, [("rec", "hello")])  # rec 看到的是链上原值

    def test_call_order_follows_plugin_order(self):
        host = PluginHost()
        log = []
        host.register(Recorder(log))

        class Second(Recorder):
            name = "rec2"
            priority = 10

        host.register(Second(log))
        host.dispatch("on_message", "x")
        self.assertEqual([t[0] for t in log], ["rec", "rec2"])

    def test_missing_hook_skipped(self):
        host = PluginHost()
        app = Appender()
        host.register(app)
        host.register(NoHooks())
        out = host.dispatch("on_message", "x")
        self.assertEqual(out, "x+app")

    def test_hook_nobody_defines_returns_payload(self):
        host = PluginHost()
        host.register(Recorder([]))
        self.assertEqual(host.dispatch("on_tick", 42), 42)

    def test_non_callable_attribute_skipped(self):
        class Weird(Plugin):
            name = "weird"
            priority = 0
            on_message = 123  # 同名属性但不可调用

        host = PluginHost()
        host.register(Weird())
        host.register(Appender())
        self.assertEqual(host.dispatch("on_message", "x"), "x+app")

    def test_snapshot_at_dispatch_start(self):
        host = PluginHost()
        host.register(Appender())

        class Spawner(Plugin):
            name = "spawner"
            priority = 5
            spawned = False

            def on_message(self, message):
                if not self.spawned:
                    host.register(Upper())  # dispatch 途中注册
                    self.spawned = True
                return message + "+spawn"

        host.register(Spawner())
        out = host.dispatch("on_message", "x")
        # 本轮用的是开始时的快照：新注册的 upper 不参与
        self.assertEqual(out, "x+spawn+app")
        self.assertEqual([p.name for p in host.plugins], ["spawner", "app", "upper"])
        # 下一轮才参与
        self.assertEqual(host.dispatch("on_message", "y"), "Y+SPAWN+APP")


class TestExamplePlugins(unittest.TestCase):
    def test_collapse_repeats_keeps_first_of_run(self):
        p = CollapseRepeats()
        seq = ["a", "a", "b", "b", "b", "a"]
        passed = [x for x in (p.on_message(m) for m in seq) if x is not None]
        self.assertEqual(passed, ["a", "b", "a"])

    def test_audit_trail_records_without_change(self):
        audit = AuditTrail()
        self.assertIsNone(audit.on_message("m1"))
        self.assertEqual(audit.seen, ["m1"])


if __name__ == "__main__":
    unittest.main()
