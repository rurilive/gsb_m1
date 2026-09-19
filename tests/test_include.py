"""include 节点行为测试：注册表展开、同上下文、深度上限与递归。"""

import unittest

from templet import Engine, TemplateCycleError, TemplateError, TemplateSyntaxError


class TestIncludeBasic(unittest.TestCase):
    def test_include_registered_template(self):
        e = Engine()
        e.register("head", "<head>{{ title }}</head>")
        out = e.render_string('{% include "head" %}', {"title": "首页"})
        self.assertEqual(out, "<head>首页</head>")

    def test_include_inlined_among_text(self):
        e = Engine()
        e.register("part", "P")
        out = e.render_string('A{% include "part" %}B')
        self.assertEqual(out, "APB")

    def test_include_output_not_double_escaped(self):
        e = Engine()
        e.register("part", "<b>{{ x }}</b>")
        out = e.render_string('{% include "part" %}', {"x": "a&b"})
        self.assertEqual(out, "<b>a&amp;b</b>")

    def test_include_same_context_no_new_scope(self):
        e = Engine()
        e.register("part", "{{ title }}/{{ user.name }}")
        out = e.render_string('{% include "part" %}',
                              {"title": "T", "user": {"name": "Li"}})
        self.assertEqual(out, "T/Li")

    def test_loop_variable_visible_in_included_template(self):
        e = Engine()
        e.register("row", "[{{ item }}]")
        out = e.render_string('{% for item in xs %}{% include "row" %}{% endfor %}',
                              {"xs": [1, 2]})
        self.assertEqual(out, "[1][2]")

    def test_nested_include_sees_outer_variables(self):
        e = Engine()
        e.register("inner", "{{ outer }}-{{ middle }}")
        e.register("middle", "({% include \"inner\" %})")
        out = e.render_string('{% include "middle" %}', {"outer": "O", "middle": "M"})
        self.assertEqual(out, "(O-M)")


class TestIncludeMissing(unittest.TestCase):
    def test_unregistered_raises_keyerror(self):
        e = Engine()
        with self.assertRaises(KeyError):
            e.render_string('{% include "nope.html" %}')

    def test_keyerror_name_is_template_name(self):
        e = Engine()
        try:
            e.render_string('{% include "missing.html" %}')
        except KeyError as exc:
            self.assertEqual(exc.args[0], "missing.html")
        else:
            self.fail("应当抛 KeyError")


class TestIncludeSyntax(unittest.TestCase):
    def test_single_quote_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include 'a.html' %}")

    def test_variable_arg_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include name %}')

    def test_missing_arg_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include %}')

    def test_extra_arg_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include "a" extra %}')

    def test_cycle_error_is_template_error(self):
        self.assertTrue(issubclass(TemplateCycleError, TemplateError))


class TestIncludeDepth(unittest.TestCase):
    def test_chain_at_depth_boundary_renders(self):
        e = Engine(max_include_depth=2)
        e.register("a", 'A{% include "b" %}')
        e.register("b", "B")
        self.assertEqual(e.render_string('{% include "a" %}'), "AB")

    def test_chain_beyond_boundary_raises(self):
        e = Engine(max_include_depth=2)
        e.register("a", 'A{% include "b" %}')
        e.register("b", 'B{% include "c" %}')
        e.register("c", "C")
        with self.assertRaises(TemplateCycleError):
            e.render_string('{% include "a" %}')

    def test_direct_recursion_raises_cycle_error(self):
        e = Engine(max_include_depth=3)
        e.register("loop", '{% include "loop" %}')
        with self.assertRaises(TemplateCycleError):
            e.render_string('{% include "loop" %}')

    def test_indirect_recursion_raises_cycle_error(self):
        e = Engine(max_include_depth=4)
        e.register("a", '{% include "b" %}')
        e.register("b", '{% include "a" %}')
        with self.assertRaises(TemplateCycleError):
            e.render_string('{% include "a" %}')

    def test_default_depth_limit_caps_recursion(self):
        e = Engine()
        e.register("loop", '{% include "loop" %}')
        with self.assertRaises(TemplateCycleError):
            e.render_string('{% include "loop" %}')

    def test_depth_limit_zero_forbids_any_include(self):
        e = Engine(max_include_depth=0)
        e.register("part", "x")
        with self.assertRaises(TemplateCycleError):
            e.render_string('{% include "part" %}')

    def test_depth_resets_between_renders(self):
        e = Engine(max_include_depth=1)
        e.register("part", "x")
        self.assertEqual(e.render_string('{% include "part" %}'), "x")
        self.assertEqual(e.render_string('{% include "part" %}'), "x")


if __name__ == "__main__":
    unittest.main()
