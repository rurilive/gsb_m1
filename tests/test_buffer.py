"""编辑缓冲的既有行为锁定：替换语义、越界、整段重扫。"""

import unittest

from lexbend import (
    BufferError,
    COMMENT,
    EOF,
    ERROR,
    IDENT,
    NUMBER,
    OP,
    STRING,
    TextBuffer,
    keys,
    scan,
)


def shape(tokens):
    return [(t.kind, t.text) for t in tokens]


class ReplaceTest(unittest.TestCase):
    def test_insert_in_middle(self):
        buf = TextBuffer("ab")
        self.assertEqual(buf.insert(1, "XY"), (0, 2))
        self.assertEqual(buf.text(), "aXYb")
        self.assertEqual(len(buf), 4)

    def test_replace_range(self):
        buf = TextBuffer("abc")
        self.assertEqual(buf.replace(1, 2, "ZZ"), (1, 2))
        self.assertEqual(buf.text(), "aZZc")

    def test_delete_range(self):
        buf = TextBuffer("abcd")
        self.assertEqual(buf.delete(1, 3), (2, 0))
        self.assertEqual(buf.text(), "ad")

    def test_replace_with_empty_keeps_text(self):
        buf = TextBuffer("ab")
        self.assertEqual(buf.replace(1, 1, ""), (0, 0))
        self.assertEqual(buf.text(), "ab")

    def test_bounds_are_rejected(self):
        buf = TextBuffer("ab")
        for start, end in ((-1, 0), (0, 3), (2, 1)):
            with self.assertRaises(BufferError):
                buf.replace(start, end, "x")
        self.assertEqual(buf.text(), "ab")

    def test_insert_at_ends(self):
        buf = TextBuffer("m")
        buf.insert(0, "<")
        buf.insert(len(buf), ">")
        self.assertEqual(buf.text(), "<m>")


class LineColTest(unittest.TestCase):
    def test_line_col_basics(self):
        buf = TextBuffer("ab\ncd")
        self.assertEqual(buf.line_col(0), (1, 1))
        self.assertEqual(buf.line_col(2), (1, 3))
        self.assertEqual(buf.line_col(3), (2, 1))
        self.assertEqual(buf.line_col(5), (2, 3))

    def test_line_col_tracks_edits(self):
        buf = TextBuffer("ab")
        buf.insert(1, "\n")
        self.assertEqual(buf.line_col(3), (2, 2))

    def test_offset_out_of_range(self):
        buf = TextBuffer("ab")
        with self.assertRaises(BufferError):
            buf.line_col(3)
        with self.assertRaises(BufferError):
            buf.line_col(-1)


class FullRescanTest(unittest.TestCase):
    def test_scan_reflects_edits(self):
        buf = TextBuffer("x = 1")
        buf.replace(2, 3, "==")
        self.assertEqual(shape(buf.scan()), [
            (IDENT, "x"), (OP, "=="), (NUMBER, "1"), (EOF, ""),
        ])
        self.assertEqual(keys(buf.scan()), keys(scan("x == 1")))

    def test_scan_count_grows_per_keystroke(self):
        buf = TextBuffer("")
        for ch in "a=1":
            buf.insert(len(buf), ch)
            buf.scan()
        self.assertEqual(buf.scan_count, 3)
        self.assertEqual(buf.text(), "a=1")

    def test_typing_matches_one_shot_scan(self):
        buf = TextBuffer("")
        typed = 'a = "h'
        for offset, ch in enumerate(typed):
            buf.insert(offset, ch)
        self.assertEqual(keys(buf.scan()), keys(scan(typed)))

    def test_closing_quote_fixes_error_token(self):
        buf = TextBuffer('v = "word')
        self.assertEqual(shape(buf.scan()), [
            (IDENT, "v"), (OP, "="), (ERROR, '"word'), (EOF, ""),
        ])
        buf.insert(len(buf), '"')
        self.assertEqual(shape(buf.scan()), [
            (IDENT, "v"), (OP, "="), (STRING, '"word"'), (EOF, ""),
        ])
        self.assertEqual(keys(buf.scan()), keys(scan('v = "word"')))

    def test_removing_comment_open_reveals_code(self):
        buf = TextBuffer("x = 1 /* y */")
        self.assertEqual(shape(buf.scan()), [
            (IDENT, "x"), (OP, "="), (NUMBER, "1"), (COMMENT, "/* y */"), (EOF, ""),
        ])
        buf.replace(6, 8, "")
        self.assertEqual(shape(buf.scan()), [
            (IDENT, "x"), (OP, "="), (NUMBER, "1"),
            (IDENT, "y"), (OP, "*"), (OP, "/"), (EOF, ""),
        ])


if __name__ == "__main__":
    unittest.main()
