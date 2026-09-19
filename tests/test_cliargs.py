"""argmini 行为清单——重构期间一个字都不改，必须原样全绿。"""

import io
import unittest
from contextlib import redirect_stdout

from argmini import ArgsError, Parser

PACK_HELP = """\
打包工具

usage: pack [-v] [-o OUT] [--level LEVEL] [-I INCLUDE] [-h] src [files ...]

positional:
  src    源文件
  files  更多文件

options:
  -v, --verbose          详细输出
  -o, --out OUT          输出文件
  --level LEVEL          压缩等级
  -I, --include INCLUDE  包含目录
  -h, --help             显示本帮助
"""

TINY_HELP = """\
usage: tiny [-v] [-h]

options:
  -v, --verbose  开关
  -h, --help     显示本帮助
"""


def build():
    p = Parser("pack", "打包工具")
    p.add("-v", "--verbose", action="store_true", help="详细输出")
    p.add("-o", "--out", default="a.out", help="输出文件")
    p.add("--level", type=int, default=1, help="压缩等级")
    p.add("-I", "--include", action="append", help="包含目录")
    p.add("src", help="源文件")
    p.add("files", nargs="*", help="更多文件")
    return p


class TestPositional(unittest.TestCase):
    def test_single_positional_full_defaults(self):
        self.assertEqual(
            build().parse(["a.txt"]),
            {"verbose": False, "out": "a.out", "level": 1,
             "include": None, "src": "a.txt", "files": []})

    def test_star_collects_rest(self):
        self.assertEqual(build().parse(["a", "b", "c"])["files"], ["b", "c"])

    def test_star_empty(self):
        self.assertEqual(build().parse(["a"])["files"], [])

    def test_two_singles_in_order(self):
        p = Parser("cp")
        p.add("src")
        p.add("dst")
        r = p.parse(["x", "y"])
        self.assertEqual(r["src"], "x")
        self.assertEqual(r["dst"], "y")

    def test_lone_dash_is_positional(self):
        self.assertEqual(build().parse(["-"])["src"], "-")

    def test_option_after_positional(self):
        r = build().parse(["a", "-v", "b"])
        self.assertEqual(r["src"], "a")
        self.assertIs(r["verbose"], True)
        self.assertEqual(r["files"], ["b"])


class TestOptions(unittest.TestCase):
    def test_flag_default_false_and_set(self):
        self.assertIs(build().parse(["a"])["verbose"], False)
        self.assertIs(build().parse(["-v", "a"])["verbose"], True)
        self.assertIs(build().parse(["--verbose", "a"])["verbose"], True)

    def test_long_space_value(self):
        self.assertEqual(build().parse(["--out", "b.bin", "a"])["out"], "b.bin")

    def test_long_eq_value(self):
        self.assertEqual(build().parse(["--out=b.bin", "a"])["out"], "b.bin")

    def test_long_eq_empty_value(self):
        self.assertEqual(build().parse(["--out=", "a"])["out"], "")

    def test_short_space_value(self):
        self.assertEqual(build().parse(["-o", "b.bin", "a"])["out"], "b.bin")

    def test_short_consumes_next_token_raw(self):
        r = build().parse(["-o", "--verbose", "a"])
        self.assertEqual(r["out"], "--verbose")
        self.assertIs(r["verbose"], False)

    def test_aliases_share_dest(self):
        r = build().parse(["-I", "x", "--include=inc2", "a"])
        self.assertEqual(r["include"], ["x", "inc2"])

    def test_append_default_when_absent(self):
        p = Parser("t")
        p.add("-I", "--include", action="append", default=[])
        p.add("src")
        r = p.parse(["a"])
        self.assertEqual(r["include"], [])

    def test_append_does_not_mutate_default(self):
        src_list = []
        p = Parser("t")
        p.add("-I", "--include", action="append", default=src_list)
        p.add("src")
        r = p.parse(["-I", "x", "a"])
        self.assertEqual(r["include"], ["x"])
        self.assertEqual(src_list, [])
        r2 = p.parse(["a"])
        self.assertEqual(r2["include"], [])

    def test_type_int_space_form(self):
        self.assertEqual(build().parse(["--level", "7", "a"])["level"], 7)

    def test_type_int_eq_form(self):
        self.assertEqual(build().parse(["--level=7", "a"])["level"], 7)

    def test_dest_from_long_alias_hyphen(self):
        p = Parser("t")
        p.add("--out-path", default="x")
        self.assertEqual(p.parse([])["out_path"], "x")

    def test_dest_explicit(self):
        p = Parser("t")
        p.add("-o", "--output", dest="out")
        p.add("src")
        self.assertEqual(p.parse(["-o", "z", "a"])["out"], "z")

    def test_dest_from_short_only(self):
        p = Parser("t")
        p.add("-q", action="store_true")
        self.assertEqual(p.parse(["-q"])["q"], True)

    def test_double_dash_terminator(self):
        r = build().parse(["--", "-v", "b"])
        self.assertEqual(r["src"], "-v")
        self.assertEqual(r["files"], ["b"])
        self.assertIs(r["verbose"], False)

    def test_options_interleaved(self):
        r = build().parse(["-v", "a", "-o", "z", "b"])
        self.assertIs(r["verbose"], True)
        self.assertEqual(r["out"], "z")
        self.assertEqual(r["src"], "a")
        self.assertEqual(r["files"], ["b"])


class TestErrors(unittest.TestCase):
    def test_unknown_long(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["--frob", "a"])
        self.assertEqual(str(ctx.exception), "unknown option: --frob")

    def test_unknown_short(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["-x", "a"])
        self.assertEqual(str(ctx.exception), "unknown option: -x")

    def test_unknown_in_eq_form(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["--frob=1", "a"])
        self.assertEqual(str(ctx.exception), "unknown option: --frob")

    def test_missing_value_long(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["--out"])
        self.assertEqual(str(ctx.exception), "missing value for --out")

    def test_missing_value_short(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["-o"])
        self.assertEqual(str(ctx.exception), "missing value for -o")

    def test_missing_required_positional(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse([])
        self.assertEqual(str(ctx.exception), "missing required argument: src")

    def test_unexpected_extra_positional(self):
        p = Parser("cp")
        p.add("src")
        p.add("dst")
        with self.assertRaises(ArgsError) as ctx:
            p.parse(["a", "b", "c"])
        self.assertEqual(str(ctx.exception), "unexpected argument: c")

    def test_flag_rejects_eq_value(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["--verbose=1", "a"])
        self.assertEqual(str(ctx.exception), "--verbose does not take a value")

    def test_invalid_int_space_form(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["--level", "abc", "a"])
        self.assertEqual(str(ctx.exception), "invalid value for --level: 'abc'")

    def test_invalid_int_eq_form(self):
        with self.assertRaises(ArgsError) as ctx:
            build().parse(["--level=abc", "a"])
        self.assertEqual(str(ctx.exception), "invalid value for --level: 'abc'")

    def test_args_error_is_exception(self):
        self.assertTrue(issubclass(ArgsError, Exception))


class TestHelp(unittest.TestCase):
    def test_help_text_exact(self):
        self.assertEqual(build().help(), PACK_HELP)

    def test_tiny_help_exact(self):
        p = Parser("tiny")
        p.add("-v", "--verbose", action="store_true", help="开关")
        self.assertEqual(p.help(), TINY_HELP)

    def test_parse_short_help_prints_and_exits(self):
        out = io.StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                build().parse(["-h"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(out.getvalue(), PACK_HELP)

    def test_parse_long_help_prints_and_exits(self):
        out = io.StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit):
                build().parse(["a.txt", "--help"])
        self.assertEqual(out.getvalue(), PACK_HELP)


if __name__ == "__main__":
    unittest.main()
