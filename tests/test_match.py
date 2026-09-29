"""routez 现有朴素线性匹配行为的锁定测试。

这一组用例只锁住改造前就成立、改造后也必须继续成立的事实：
纯静态路径逐段全等才算命中，命中给出注册时挂的处理体与空参数表，
未命中返回 None；重复注册同一路径报错；注销后不再命中；非法路径
在注册与查找时都要立刻失败。所有路径都是字面静态段，不涉及参数、
通配与优先级，因此这批断言在树化改造后依旧成立。
"""

import unittest

from routez import Router
from routez.router import Match, split_path


def _h(name):
    return lambda *a, **k: name


class TestSplitPath(unittest.TestCase):
    def test_root_is_empty_segments(self):
        self.assertEqual(split_path("/"), [])

    def test_single_segment(self):
        self.assertEqual(split_path("/a"), ["a"])

    def test_nested_segments(self):
        self.assertEqual(split_path("/a/b/c"), ["a", "b", "c"])

    def test_missing_leading_slash_rejected(self):
        with self.assertRaises(ValueError):
            split_path("a/b")

    def test_empty_string_rejected(self):
        with self.assertRaises(ValueError):
            split_path("")

    def test_empty_segment_rejected(self):
        with self.assertRaises(ValueError):
            split_path("/a//b")

    def test_trailing_slash_rejected(self):
        with self.assertRaises(ValueError):
            split_path("/a/")


class TestStaticMatch(unittest.TestCase):
    def setUp(self):
        self.r = Router()
        self.r.add("/", _h("root"))
        self.r.add("/users", _h("users"))
        self.r.add("/users/list", _h("list"))

    def test_exact_static_hit(self):
        m = self.r.match("/users")
        self.assertEqual(m.handler(), "users")

    def test_hit_returns_match_instance(self):
        self.assertIsInstance(self.r.match("/users"), Match)

    def test_hit_has_empty_params(self):
        self.assertEqual(self.r.match("/users").params, {})

    def test_nested_static_hit(self):
        self.assertEqual(self.r.match("/users/list").handler(), "list")

    def test_root_hit(self):
        self.assertEqual(self.r.match("/").handler(), "root")

    def test_miss_returns_none(self):
        self.assertIsNone(self.r.match("/users/detail"))

    def test_prefix_is_not_a_hit(self):
        # 朴素实现只认逐段全等，/users 不会当作 /users/list 的前缀命中。
        self.assertIsNone(self.r.match("/users/list/extra"))

    def test_case_sensitive(self):
        self.assertIsNone(self.r.match("/Users"))


class TestAddRemove(unittest.TestCase):
    def test_duplicate_add_rejected(self):
        r = Router()
        r.add("/a", _h("a"))
        with self.assertRaises(ValueError):
            r.add("/a", _h("a2"))

    def test_add_illegal_path_rejected(self):
        r = Router()
        with self.assertRaises(ValueError):
            r.add("/a//b", _h("bad"))

    def test_remove_then_miss(self):
        r = Router()
        r.add("/a", _h("a"))
        r.remove("/a")
        self.assertIsNone(r.match("/a"))

    def test_remove_unknown_rejected(self):
        r = Router()
        with self.assertRaises(KeyError):
            r.remove("/nope")

    def test_match_illegal_path_rejected(self):
        r = Router()
        r.add("/a", _h("a"))
        with self.assertRaises(ValueError):
            r.match("/a//b")


class TestList(unittest.TestCase):
    def test_routes_reflects_registration(self):
        r = Router()
        r.add("/a", _h("a"))
        r.add("/b", _h("b"))
        self.assertEqual(r.routes(), ["/a", "/b"])

    def test_routes_after_remove(self):
        r = Router()
        r.add("/a", _h("a"))
        r.add("/b", _h("b"))
        r.remove("/a")
        self.assertEqual(r.routes(), ["/b"])

    def test_routes_is_a_list(self):
        r = Router()
        self.assertIsInstance(r.routes(), list)


if __name__ == "__main__":
    unittest.main()
