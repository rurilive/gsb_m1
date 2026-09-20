"""Dispatcher 现有行为的锁定测试。"""

import unittest

from idemkit import Dispatcher, NotSerializableError, UnknownTaskError


class TestRegister(unittest.TestCase):
    def test_register_and_order(self):
        d = Dispatcher()
        d.register("render", lambda p: p)
        d.register("resize", lambda p: p)
        self.assertEqual(d.handlers(), ["render", "resize"])

    def test_dup_register_raises(self):
        d = Dispatcher()
        d.register("render", lambda p: p)
        with self.assertRaises(ValueError):
            d.register("render", lambda p: p)


class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.d = Dispatcher()
        self.calls = []
        self.d.register("echo", lambda p: self.calls.append(p) or p)
        self.d.register("add", lambda p: p["a"] + p["b"])

    def test_dispatch_returns_result(self):
        self.assertEqual(self.d.dispatch("add", {"a": 2, "b": 3}), 5)

    def test_dispatch_passes_payload(self):
        self.d.dispatch("echo", {"x": 1})
        self.assertEqual(self.calls, [{"x": 1}])

    def test_unknown_task(self):
        with self.assertRaises(UnknownTaskError):
            self.d.dispatch("nope", {})

    def test_handler_exception_propagates(self):
        def boom(p):
            raise RuntimeError("disk full")

        self.d.register("boom", boom)
        with self.assertRaises(RuntimeError):
            self.d.dispatch("boom", {})

    def test_dict_result(self):
        self.d.register("meta", lambda p: {"ok": True, "n": p})
        self.assertEqual(self.d.dispatch("meta", 3), {"ok": True, "n": 3})

    def test_none_result_allowed(self):
        self.d.register("noop", lambda p: None)
        self.assertIsNone(self.d.dispatch("noop", {}))

    def test_tuple_result_rejected(self):
        self.d.register("pair", lambda p: (p, p))
        with self.assertRaises(NotSerializableError):
            self.d.dispatch("pair", 1)

    def test_object_result_rejected(self):
        class Thing:
            pass

        self.d.register("thing", lambda p: Thing())
        with self.assertRaises(NotSerializableError):
            self.d.dispatch("thing", None)


if __name__ == "__main__":
    unittest.main()
