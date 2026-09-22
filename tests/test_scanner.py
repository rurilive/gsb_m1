"""全量扫描的既有行为锁定：类别、区间、行列、错误 token 的形状。"""

import unittest

from lexbend import (
    COMMENT,
    EOF,
    ERROR,
    IDENT,
    NUMBER,
    OP,
    STRING,
    keys,
    scan,
)


def shape(text):
    """(种类, 原文) 序列，省略位置，测试里看得清楚些。"""
    return [(t.kind, t.text) for t in scan(text)]


class ScanShapeTest(unittest.TestCase):
    def test_empty_text(self):
        tokens = scan("")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].kind, EOF)
        self.assertEqual(tokens[0].text, "")

    def test_whitespace_only(self):
        tokens = scan(" \t \r ")
        self.assertEqual([t.kind for t in tokens], [EOF])

    def test_ident_number(self):
        self.assertEqual(shape("abc 12 3.5 _x1"), [
            (IDENT, "abc"), (NUMBER, "12"), (NUMBER, "3.5"), (IDENT, "_x1"), (EOF, ""),
        ])

    def test_number_then_dot(self):
        self.assertEqual(shape("1."), [(NUMBER, "1"), (OP, "."), (EOF, "")])
        self.assertEqual(shape("1.x"), [(NUMBER, "1"), (OP, "."), (IDENT, "x"), (EOF, "")])

    def test_operators_longest_match(self):
        self.assertEqual(shape("a<=b != c -> d"), [
            (IDENT, "a"), (OP, "<="), (IDENT, "b"), (OP, "!="), (IDENT, "c"),
            (OP, "->"), (IDENT, "d"), (EOF, ""),
        ])

    def test_single_and_double_operators(self):
        self.assertEqual(shape("= == < <"), [
            (OP, "="), (OP, "=="), (OP, "<"), (OP, "<"), (EOF, ""),
        ])

    def test_slash_stays_operator(self):
        self.assertEqual(shape("a / b"), [
            (IDENT, "a"), (OP, "/"), (IDENT, "b"), (EOF, ""),
        ])

    def test_string_with_escapes(self):
        self.assertEqual(shape('say "a\\"b\\\\" end'), [
            (IDENT, "say"), (STRING, '"a\\"b\\\\"'), (IDENT, "end"), (EOF, ""),
        ])

    def test_line_comment_keeps_newline_out(self):
        self.assertEqual(shape("x # note\ny"), [
            (IDENT, "x"), (COMMENT, "# note"), (IDENT, "y"), (EOF, ""),
        ])

    def test_block_comment_multiline(self):
        self.assertEqual(shape("a /* one\ntwo */ b"), [
            (IDENT, "a"), (COMMENT, "/* one\ntwo */"), (IDENT, "b"), (EOF, ""),
        ])

    def test_unterminated_string_stops_before_newline(self):
        self.assertEqual(shape('x = "abc\ny = 2'), [
            (IDENT, "x"), (OP, "="), (ERROR, '"abc'),
            (IDENT, "y"), (OP, "="), (NUMBER, "2"), (EOF, ""),
        ])

    def test_unterminated_string_at_eof(self):
        self.assertEqual(shape('x = "abc'), [
            (IDENT, "x"), (OP, "="), (ERROR, '"abc'), (EOF, ""),
        ])

    def test_unclosed_block_comment_swallows_rest(self):
        self.assertEqual(shape("a /* open\nb = 1"), [
            (IDENT, "a"), (ERROR, "/* open\nb = 1"), (EOF, ""),
        ])

    def test_illegal_chars_do_not_clump(self):
        self.assertEqual(shape("a @ $ b"), [
            (IDENT, "a"), (ERROR, "@"), (ERROR, "$"), (IDENT, "b"), (EOF, ""),
        ])

    def test_dollar_inside_string_is_fine(self):
        self.assertEqual(shape('x = "a$b"'), [
            (IDENT, "x"), (OP, "="), (STRING, '"a$b"'), (EOF, ""),
        ])


class ScanPositionTest(unittest.TestCase):
    def test_positions_on_first_line(self):
        tokens = scan("ab + 12")
        self.assertEqual([(t.start, t.end) for t in tokens],
                         [(0, 2), (3, 4), (5, 7), (7, 7)])
        self.assertEqual([(t.line, t.col) for t in tokens],
                         [(1, 1), (1, 4), (1, 6), (1, 8)])

    def test_positions_across_lines(self):
        tokens = scan("ab\n  cd\n")
        self.assertEqual([(t.kind, t.line, t.col) for t in tokens], [
            (IDENT, 1, 1), (IDENT, 2, 3), (EOF, 3, 1),
        ])
        self.assertEqual(tokens[1].text, "cd")

    def test_eof_sits_at_the_end(self):
        text = "a\nbc"
        tokens = scan(text)
        tail = tokens[-1]
        self.assertEqual(tail.kind, EOF)
        self.assertEqual((tail.start, tail.end), (len(text), len(text)))
        self.assertEqual((tail.line, tail.col), (2, 3))

    def test_unterminated_string_next_line_starts_over(self):
        tokens = scan('"abc\ny')
        self.assertEqual([(t.kind, t.line, t.col) for t in tokens], [
            (ERROR, 1, 1), (IDENT, 2, 1), (EOF, 2, 2),
        ])
        self.assertEqual(tokens[0].end, 4)

    def test_multiline_comment_line_numbers(self):
        tokens = scan("/* a\nb\nc */ x")
        self.assertEqual((tokens[0].line, tokens[0].col), (1, 1))
        self.assertEqual((tokens[1].line, tokens[1].col), (3, 6))
        self.assertEqual(tokens[0].text, "/* a\nb\nc */")


class ScanKeyTest(unittest.TestCase):
    def test_keys_mirror_tokens(self):
        tokens = scan("a=1")
        self.assertEqual(keys(tokens), [
            (IDENT, "a", 0, 1, 1, 1),
            (OP, "=", 1, 2, 1, 2),
            (NUMBER, "1", 2, 3, 1, 3),
            (EOF, "", 3, 3, 1, 4),
        ])

    def test_keys_are_plain_tuples(self):
        token = scan("x")[0]
        self.assertEqual(token.key(), (IDENT, "x", 0, 1, 1, 1))

    def test_repr_round_trip(self):
        token = scan("7")[0]
        self.assertEqual(repr(token), "Token(NUMBER, '7', 0, 1, 1, 1)")


class ScanWholeTextTest(unittest.TestCase):
    def test_program_snippet(self):
        text = (
            "# 面积\na = 3.5 * w\n"
            'label = "cell"\n'
            "if a <= 20 { ok -> done }\n"
        )
        kinds = [t.kind for t in scan(text)]
        self.assertEqual(kinds, [
            COMMENT, IDENT, OP, NUMBER, OP, IDENT,
            IDENT, OP, STRING,
            IDENT, IDENT, OP, NUMBER, OP, IDENT, OP, IDENT, OP,
            EOF,
        ])
        self.assertEqual(scan(text)[-1].start, len(text))

    def test_error_then_recovery_in_one_pass(self):
        text = 'a = @ b\nc = "un\n'
        self.assertEqual(shape(text), [
            (IDENT, "a"), (OP, "="), (ERROR, "@"), (IDENT, "b"),
            (IDENT, "c"), (OP, "="), (ERROR, '"un'), (EOF, ""),
        ])


if __name__ == "__main__":
    unittest.main()
