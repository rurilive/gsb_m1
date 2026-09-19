"""templet 现有行为的锁定测试。"""

import unittest

from templet import Engine, TemplateError, TemplateSyntaxError
from templet.expr import UNDEFINED


def render(source, ctx=None, **kw):
    return Engine(**kw).render_string(source, ctx)


class TestBasic(unittest.TestCase):
    def test_plain_text_passthrough(self):
        self.assertEqual(render("hello world\n第二行"), "hello world\n第二行")

    def test_var_substitution(self):
        self.assertEqual(render("hi {{ name }}!", {"name": "Tom"}), "hi Tom!")

    def test_int_and_bool_render_as_str(self):
        self.assertEqual(render("{{ n }}|{{ flag }}", {"n": 42, "flag": True}), "42|True")

    def test_none_renders_as_none(self):
        self.assertEqual(render("{{ v }}", {"v": None}), "None")

    def test_undefined_var_renders_empty(self):
        self.assertEqual(render("[{{ missing }}]"), "[]")

    def test_undefined_is_falsy_in_if(self):
        self.assertEqual(render("{% if missing %}Y{% else %}N{% endif %}"), "N")

    def test_undefined_sentinel(self):
        self.assertFalse(bool(UNDEFINED))
        self.assertEqual(str(UNDEFINED), "")
        self.assertEqual(UNDEFINED, UNDEFINED)


class TestEscape(unittest.TestCase):
    def test_autoescape_default_on(self):
        out = render("{{ v }}", {"v": "<b>&\"'"})
        self.assertEqual(out, "&lt;b&gt;&amp;&quot;&#x27;")

    def test_autoescape_off(self):
        out = render("{{ v }}", {"v": "<b>"}, autoescape=False)
        self.assertEqual(out, "<b>")

    def test_safe_filter_skips_escape(self):
        self.assertEqual(render("{{ v | safe }}", {"v": "<i>x</i>"}), "<i>x</i>")

    def test_safe_anywhere_in_chain(self):
        self.assertEqual(render("{{ v | join(\"|\") | safe }}", {"v": ["<i>"]}), "<i>")

    def test_safe_with_upper_still_applies(self):
        self.assertEqual(render("{{ v | safe | upper }}", {"v": "<i>"}), "<I>")


class TestFilters(unittest.TestCase):
    def test_upper(self):
        self.assertEqual(render("{{ s | upper }}", {"s": "AbC"}), "ABC")

    def test_length(self):
        self.assertEqual(render("{{ xs | length }}", {"xs": [1, 2, 3]}), "3")

    def test_length_of_undefined_is_zero(self):
        self.assertEqual(render("{{ missing | length }}"), "0")

    def test_join_with_arg(self):
        self.assertEqual(render("{{ xs | join(\"-\") }}", {"xs": ["a", "b"]}), "a-b")

    def test_join_default_sep(self):
        self.assertEqual(render("{{ xs | join }}", {"xs": ["a", 1]}), "a, 1")

    def test_join_pipe_inside_arg_not_split(self):
        self.assertEqual(render("{{ xs | join(\"|\") }}", {"xs": ["a", "b"]}), "a|b")

    def test_default_on_undefined_and_empty(self):
        self.assertEqual(render("{{ m | default(\"D\") }}/{{ e | default(\"D\") }}",
                                {"e": ""}), "D/D")

    def test_unknown_filter_raises_template_error(self):
        with self.assertRaises(TemplateError):
            render("{{ v | nosuch }}", {"v": 1})

    def test_filter_arg_must_be_literal(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{{ xs | join(other) }}", {"xs": [], "other": "-"})


class TestAccess(unittest.TestCase):
    def test_dict_attr_and_subscript(self):
        ctx = {"u": {"name": "Li", "tags": ["a", "b"]}}
        self.assertEqual(render("{{ u.name }}/{{ u[\"tags\"][1] }}", ctx), "Li/b")

    def test_attr_falls_back_to_getattr(self):
        out = render("{{ s.upper }}", {"s": "ab"}, autoescape=False)
        self.assertTrue(out.startswith("<built-in method upper"))

    def test_missing_attr_is_undefined(self):
        self.assertEqual(render("[{{ u.nope }}]", {"u": {}}), "[]")

    def test_missing_key_is_undefined(self):
        self.assertEqual(render("[{{ u[99] }}]", {"u": {}}), "[]")

    def test_underscore_attr_blocked(self):
        ctx = {"o": {"_secret": 1}}
        self.assertEqual(render("{{ o._secret }}", ctx), "")
        self.assertEqual(render("{{ o.__class__ }}", ctx), "")

    def test_comparison_with_undefined_is_false(self):
        self.assertEqual(render("{% if missing == 1 %}Y{% else %}N{% endif %}"), "N")


class TestFor(unittest.TestCase):
    def test_loop_list(self):
        out = render("{% for x in xs %}<{{ x }}>{% endfor %}", {"xs": [1, 2]})
        self.assertEqual(out, "<1><2>")

    def test_loop_dict_iterates_keys(self):
        out = render("{% for k in d %}{{ k }};{% endfor %}", {"d": {"a": 1, "b": 2}})
        self.assertEqual(out, "a;b;")

    def test_tuple_unpack(self):
        out = render("{% for k, v in ps %}{{ k }}={{ v }};{% endfor %}",
                     {"ps": [("a", 1), ("b", 2)]})
        self.assertEqual(out, "a=1;b=2;")

    def test_unpack_length_mismatch_raises(self):
        with self.assertRaises(TemplateError):
            render("{% for a, b in ps %}{{ a }}{% endfor %}", {"ps": [(1, 2, 3)]})

    def test_empty_iterable_no_body(self):
        self.assertEqual(render("A{% for x in xs %}B{% endfor %}C", {"xs": []}), "AC")

    def test_undefined_iterable_no_body(self):
        self.assertEqual(render("A{% for x in missing %}B{% endfor %}C"), "AC")

    def test_loop_var_scoped(self):
        out = render("{% for x in xs %}{% endfor %}[{{ x }}]", {"xs": [1]})
        self.assertEqual(out, "[]")

    def test_nested_for_and_attr(self):
        out = render("{% for u in us %}{% for t in u.tags %}{{ u.name }}:{{ t }};{% endfor %}{% endfor %}",
                     {"us": [{"name": "Li", "tags": ["x", "y"]}]})
        self.assertEqual(out, "Li:x;Li:y;")


class TestIf(unittest.TestCase):
    def test_truthy_and_falsy(self):
        self.assertEqual(render("{% if v %}Y{% else %}N{% endif %}", {"v": 1}), "Y")
        self.assertEqual(render("{% if v %}Y{% else %}N{% endif %}", {"v": ""}), "N")
        self.assertEqual(render("{% if v %}Y{% else %}N{% endif %}", {"v": 0}), "N")

    def test_comparisons(self):
        cases = [("1 == 1", "Y"), ("1 != 1", "N"), ("2 > 1", "Y"),
                 ("1 >= 2", "N"), ("'a' < 'b'", "Y")]
        for cond, want in cases:
            self.assertEqual(
                render("{%% if %s %%}Y{%% else %%}N{%% endif %%}" % cond), want)

    def test_in_and_not_in(self):
        self.assertEqual(render("{% if x in xs %}Y{% endif %}", {"x": 2, "xs": [1, 2]}), "Y")
        self.assertEqual(render("{% if x not in xs %}Y{% endif %}", {"x": 9, "xs": [1]}), "Y")

    def test_and_or_not(self):
        self.assertEqual(render("{% if a and b %}Y{% endif %}", {"a": 1, "b": 1}), "Y")
        self.assertEqual(render("{% if not a %}Y{% else %}N{% endif %}", {"a": 0}), "Y")

    def test_or_returns_value(self):
        self.assertEqual(render("{{ missing or \"back\" }}"), "back")

    def test_if_in_for(self):
        out = render("{% for x in xs %}{% if x > 1 %}{{ x }}{% endif %}{% endfor %}",
                     {"xs": [1, 2, 3]})
        self.assertEqual(out, "23")


class TestSyntax(unittest.TestCase):
    def test_unclosed_var(self):
        with self.assertRaises(TemplateSyntaxError):
            render("hello {{ name")

    def test_unclosed_tag(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% if x %}hi")

    def test_unknown_tag(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% while x %}{% endwhile %}")

    def test_stray_endfor(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% endfor %}")

    def test_stray_endif(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% endif %}")

    def test_stray_else(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% else %}")

    def test_for_missing_in(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% for x xs %}{% endfor %}")

    def test_for_without_endfor(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% for x in xs %}{{ x }}")

    def test_if_without_endif(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% if x %}y")

    def test_empty_tag(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{% %}")

    def test_bad_expression(self):
        with self.assertRaises(TemplateSyntaxError):
            render("{{ a + }}")

    def test_syntax_error_is_template_error(self):
        self.assertTrue(issubclass(TemplateSyntaxError, TemplateError))


class TestEngine(unittest.TestCase):
    def test_register_and_render(self):
        e = Engine()
        e.register("greet", "hi {{ name }}")
        self.assertEqual(e.render("greet", {"name": "A"}), "hi A")

    def test_unknown_template_keyerror(self):
        with self.assertRaises(KeyError):
            Engine().render("nope")

    def test_register_overrides(self):
        e = Engine()
        e.register("t", "one")
        e.register("t", "two")
        self.assertEqual(e.render("t"), "two")

    def test_render_string_not_in_registry(self):
        e = Engine()
        e.render_string("x")
        with self.assertRaises(KeyError):
            e.render("x")

    def test_ctx_dict_not_polluted(self):
        e = Engine()
        ctx = {"xs": [1, 2]}
        e.render_string("{% for x in xs %}{% endfor %}", ctx)
        self.assertEqual(ctx, {"xs": [1, 2]})

    def test_vars_not_leaked_between_renders(self):
        e = Engine()
        e.render_string("{{ a }}", {"a": 1})
        self.assertEqual(e.render_string("{{ a }}"), "")

    def test_globals_survive_across_renders(self):
        e = Engine()
        self.assertEqual(e.render_string("{{ v }}", {"v": "ok"}), "ok")
        self.assertEqual(e.render_string("{{ v }}", {"v": "ok2"}), "ok2")

    def test_engine_filters_extendable(self):
        e = Engine()
        e.filters["shout"] = lambda v: str(v) + "!"
        self.assertEqual(e.render_string("{{ w | shout }}", {"w": "yo"}), "yo!")


if __name__ == "__main__":
    unittest.main()
