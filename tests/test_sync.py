"""朴素同步分发的锁定测试。

只覆盖当前实现已经具备的能力：注册与摘除名字、按名字同步调用处理器、
返回值原样带回、处理器异常被包装、目标不存在与重名被拒绝。新增能力
（异步邮箱、tell 投递、ask 请求应答、超时、监督重启、死信、生命周期、
并发与顺序保证）另开测试文件，本文件一字不改。
"""

import unittest

from actorbox.registry import (
    ActorError,
    DuplicateActor,
    HandlerError,
    NoSuchActor,
    Registry,
)


class TestRegister(unittest.TestCase):
    def test_register_returns_name(self):
        registry = Registry()
        self.assertEqual(registry.register("a", lambda m: m), "a")

    def test_has_and_names_follow_registration_order(self):
        registry = Registry()
        registry.register("a", lambda m: m)
        registry.register("b", lambda m: m)
        registry.register("c", lambda m: m)
        self.assertTrue(registry.has("a"))
        self.assertEqual(registry.names(), ["a", "b", "c"])

    def test_has_is_false_for_unknown(self):
        self.assertFalse(Registry().has("nope"))

    def test_duplicate_name_is_rejected(self):
        registry = Registry()
        registry.register("a", lambda m: m)
        with self.assertRaises(DuplicateActor):
            registry.register("a", lambda m: m)

    def test_register_rejects_non_callable_handler(self):
        registry = Registry()
        with self.assertRaises(ActorError):
            registry.register("a", 123)

    def test_register_rejects_empty_name(self):
        registry = Registry()
        with self.assertRaises(ActorError):
            registry.register("", lambda m: m)

    def test_unregister_removes_name(self):
        registry = Registry()
        registry.register("a", lambda m: m)
        registry.unregister("a")
        self.assertFalse(registry.has("a"))
        self.assertEqual(registry.names(), [])

    def test_unregister_unknown_is_rejected(self):
        with self.assertRaises(NoSuchActor):
            Registry().unregister("nope")


class TestSend(unittest.TestCase):
    def test_send_returns_handler_result(self):
        registry = Registry()
        registry.register("double", lambda m: m * 2)
        self.assertEqual(registry.send("double", 21), 42)

    def test_send_runs_handler_synchronously(self):
        calls = []
        registry = Registry()
        registry.register("note", lambda m: calls.append(m))
        result = registry.send("note", "x")
        self.assertEqual(calls, ["x"])
        self.assertIsNone(result)

    def test_send_passes_message_unchanged(self):
        registry = Registry()
        registry.register("id", lambda m: m)
        payload = {"k": [1, 2, 3]}
        self.assertIs(registry.send("id", payload), payload)

    def test_send_to_unknown_is_rejected(self):
        with self.assertRaises(NoSuchActor):
            Registry().send("nope", "x")

    def test_send_wraps_handler_exception(self):
        registry = Registry()

        def boom(_m):
            raise ValueError("bad")

        registry.register("boom", boom)
        with self.assertRaises(HandlerError) as ctx:
            registry.send("boom", "x")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_send_does_not_swallow_actor_error(self):
        registry = Registry()

        def raise_actor_error(_m):
            raise NoSuchActor("inner")

        registry.register("inner", raise_actor_error)
        with self.assertRaises(NoSuchActor):
            registry.send("inner", "x")

    def test_send_is_not_queued_each_call_runs_handler(self):
        calls = []
        registry = Registry()
        registry.register("count", lambda m: calls.append(m))
        registry.send("count", 1)
        registry.send("count", 2)
        self.assertEqual(calls, [1, 2])


if __name__ == "__main__":
    unittest.main()