"""{% include "name" %} 节点的行为测试。"""

import unittest

from templet import (
    Engine,
    TemplateCycleError,
    TemplateError,
    TemplateSyntaxError,
)


class TestIncludeBasic(unittest.TestCase):
    def test_include_registered_template(self):
        e = Engine()
        e.register("head.html", "[HEAD]")
        self.assertEqual(e.render_string('A{% include "head.html" %}B'), "A[HEAD]B")

    def test_include_via_render_named(self):
        e = Engine()
        e.register("part", "P")
        e.register("page", '<{% include "part" %}>')
        self.assertEqual(e.render("page"), "<P>")

    def test_whitespace_inside_tag_allowed(self):
        e = Engine()
        e.register("p", "P")
        self.assertEqual(e.render_string('{%  include   "p"  %}'), "P")

    def test_empty_name_allowed(self):
        e = Engine()
        e.register("", "EMPTY")
        self.assertEqual(e.render_string('{% include "" %}'), "EMPTY")

    def test_multiple_includes(self):
        e = Engine()
        e.register("p", "x")
        self.assertEqual(e.render_string('{% include "p" %}|{% include "p" %}'), "x|x")


class TestIncludeContext(unittest.TestCase):
    def test_outer_vars_visible(self):
        e = Engine()
        e.register("part", "hi {{ name }}")
        self.assertEqual(e.render_string('{% include "part" %}', {"name": "Tom"}),
                         "hi Tom")

    def test_nested_include_sees_outer_vars(self):
        e = Engine()
        e.register("inner", "inner:{{ v }}")
        e.register("outer", 'outer {% include "inner" %}')
        self.assertEqual(e.render_string('{% include "outer" %}', {"v": 7}),
                         "outer inner:7")

    def test_loop_var_visible_in_include(self):
        e = Engine()
        e.register("item.html", "<{{ x }}>")
        out = e.render_string(
            '{% for x in xs %}{% include "item.html" %}{% endfor %}',
            {"xs": [1, 2]})
        self.assertEqual(out, "<1><2>")

    def test_no_new_scope_vars_shared_after_include(self):
        e = Engine()
        e.register("wrap", '{% for x in xs %}[{{ x }}]{% endfor %}')
        out = e.render_string('{% include "wrap" %}/{{ x }}',
                              {"xs": ["a"], "x": "root"})
        self.assertEqual(out, "[a]/root")

    def test_included_output_not_double_escaped(self):
        e = Engine()
        e.register("part", "<b>{{ v }}</b>")
        self.assertEqual(
            e.render_string('{% include "part" %}', {"v": "<i>"}),
            "<b>&lt;i&gt;</b>")

    def test_include_inside_var_driven_flow(self):
        e = Engine()
        e.register("yes", "Y")
        e.register("no", "N")
        out = e.render_string(
            '{% if flag %}{% include "yes" %}{% else %}{% include "no" %}{% endif %}',
            {"flag": True})
        self.assertEqual(out, "Y")

    def test_autoescape_off_propagates(self):
        e = Engine(autoescape=False)
        e.register("p", "{{ v }}")
        self.assertEqual(e.render_string('{% include "p" %}', {"v": "<i>"}), "<i>")


class TestIncludeErrors(unittest.TestCase):
    def test_missing_template_raises_keyerror(self):
        e = Engine()
        with self.assertRaises(KeyError):
            e.render_string('{% include "nope.html" %}')

    def test_missing_template_keyerror_is_name(self):
        e = Engine()
        with self.assertRaises(KeyError) as cm:
            e.render_string('{% include "nope.html" %}')
        self.assertEqual(cm.exception.args[0], "nope.html")

    def test_missing_nested_template_raises_keyerror(self):
        e = Engine()
        e.register("outer", '{% include "ghost.html" %}')
        with self.assertRaises(KeyError):
            e.render_string('{% include "outer" %}')

    def test_single_quote_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include 'a.html' %}")

    def test_unquoted_name_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include name %}')

    def test_missing_argument_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include %}")

    def test_trailing_junk_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include "a.html" extra %}')

    def test_double_quotes_only_no_concat(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include "a" + "b" %}')


class TestIncludeDepth(unittest.TestCase):
    def test_default_depth_limit(self):
        self.assertEqual(Engine().max_include_depth, 10)
        self.assertEqual(Engine.DEFAULT_MAX_INCLUDE_DEPTH, 10)

    def test_direct_recursion_raises_cycle(self):
        e = Engine(max_include_depth=5)
        e.register("loop", '{% include "loop" %}')
        with self.assertRaises(TemplateCycleError):
            e.render("loop")

    def test_indirect_recursion_raises_cycle(self):
        e = Engine(max_include_depth=10)
        e.register("a", 'A{% include "b" %}')
        e.register("b", 'B{% include "a" %}')
        with self.assertRaises(TemplateCycleError):
            e.render("a")

    def test_boundary_allows_exactly_n_expansions(self):
        e = Engine(max_include_depth=2)
        e.register("l1", 'L1{% include "l2" %}')
        e.register("l2", 'L2{% include "l3" %}')
        e.register("l3", "L3")
        self.assertEqual(e.render("l1"), "L1L2L3")

    def test_boundary_one_beyond_raises(self):
        e = Engine(max_include_depth=2)
        e.register("l1", 'L1{% include "l2" %}')
        e.register("l2", 'L2{% include "l3" %}')
        e.register("l3", 'L3{% include "l4" %}')
        e.register("l4", "L4")
        with self.assertRaises(TemplateCycleError):
            e.render("l1")

    def test_depth_one_allows_single_include(self):
        e = Engine(max_include_depth=1)
        e.register("p", "P")
        self.assertEqual(e.render_string('{% include "p" %}'), "P")

    def test_depth_one_blocks_nested(self):
        e = Engine(max_include_depth=1)
        e.register("outer", '{% include "inner" %}')
        e.register("inner", "INNER")
        with self.assertRaises(TemplateCycleError):
            e.render_string('{% include "outer" %}')

    def test_sibling_includes_do_not_accumulate(self):
        e = Engine(max_include_depth=1)
        e.register("p", "P")
        self.assertEqual(
            e.render_string('{% include "p" %}{% include "p" %}'), "PP")

    def test_depth_resets_between_renders(self):
        e = Engine(max_include_depth=1)
        e.register("p", "P")
        self.assertEqual(e.render_string('{% include "p" %}'), "P")
        self.assertEqual(e.render_string('{% include "p" %}'), "P")

    def test_cycle_error_is_template_error(self):
        self.assertTrue(issubclass(TemplateCycleError, TemplateError))


if __name__ == "__main__":
    unittest.main()
