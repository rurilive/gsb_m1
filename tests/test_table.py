"""texttbl.render 行为清单——重构期间一个字都不改，必须原样全绿。"""

import unittest

from texttbl import Table


class TestStyles(unittest.TestCase):
    def test_ascii_basic(self):
        t = Table(["service", "qps", "p95"], style="ascii")
        t.add_row("gateway", "18230", "12.4").add_row("auth", "4310", "3.1").add_row(
            "billing", "872", "55.9"
        )
        self.assertEqual(
            t.render(),
            "+---------+-------+------+\n"
            "| service | qps   | p95  |\n"
            "+---------+-------+------+\n"
            "| gateway | 18230 | 12.4 |\n"
            "| auth    | 4310  | 3.1  |\n"
            "| billing | 872   | 55.9 |\n"
            "+---------+-------+------+",
        )

    def test_ascii_empty_table(self):
        self.assertEqual(
            Table(["a", "bb"]).render(),
            "+---+----+\n| a | bb |\n+---+----+",
        )

    def test_light_basic(self):
        t = Table(["service", "qps", "p95"], style="light")
        t.add_row("gateway", "18230", "12.4").add_row("auth", "4310", "3.1")
        self.assertEqual(
            t.render(),
            "┌─────────┬───────┬──────┐\n"
            "│ service │ qps   │ p95  │\n"
            "├─────────┼───────┼──────┤\n"
            "│ gateway │ 18230 │ 12.4 │\n"
            "│ auth    │ 4310  │ 3.1  │\n"
            "└─────────┴───────┴──────┘",
        )

    def test_heavy_basic(self):
        t = Table(["service", "qps", "p95"], style="heavy")
        t.add_row("gateway", "18230", "12.4")
        self.assertEqual(
            t.render(),
            "┏━━━━━━━━━┳━━━━━━━┳━━━━━━┓\n"
            "┃ service ┃ qps   ┃ p95  ┃\n"
            "┣━━━━━━━━━╋━━━━━━━╋━━━━━━┫\n"
            "┃ gateway ┃ 18230 ┃ 12.4 ┃\n"
            "┗━━━━━━━━━┻━━━━━━━┻━━━━━━┛",
        )

    def test_markdown_basic(self):
        t = Table(["service", "qps", "p95"], style="markdown")
        t.add_row("gateway", "18230", "12.4").add_row("auth", "4310", "3.1")
        self.assertEqual(
            t.render(),
            "| service | qps   | p95  |\n"
            "| ------- | ----- | ---- |\n"
            "| gateway | 18230 | 12.4 |\n"
            "| auth    | 4310  | 3.1  |",
        )

    def test_markdown_empty_table(self):
        # markdown 分隔行的横线数=列宽（不是固定 3 个）
        self.assertEqual(
            Table(["a", "bb"], style="markdown").render(),
            "| a | bb |\n| - | -- |",
        )

    def test_unknown_style_raises_at_render(self):
        t = Table(["a"], style="fancy")
        t.add_row("x")
        with self.assertRaises(ValueError) as ctx:
            t.render()
        self.assertEqual(str(ctx.exception), "unknown style: 'fancy'")

    def test_default_style_is_ascii(self):
        self.assertEqual(
            Table(["x"]).render(),
            "+---+\n| x |\n+---+",
        )

    def test_width_follows_longest_cell(self):
        t = Table(["h"])
        t.add_row("loooooong")
        self.assertEqual(
            t.render(),
            "+-----------+\n| h         |\n+-----------+\n| loooooong |\n+-----------+",
        )


class TestRows(unittest.TestCase):
    def test_fewer_cells_blank_filled(self):
        t = Table(["a", "b"])
        t.add_row("x")
        self.assertEqual(
            t.render(),
            "+---+---+\n| a | b |\n+---+---+\n| x |   |\n+---+---+",
        )

    def test_too_many_cells_raises(self):
        t = Table(["a", "b"])
        with self.assertRaises(ValueError) as ctx:
            t.add_row("x", "y", "z")
        self.assertEqual(str(ctx.exception), "too many cells: got 3, want 2")

    def test_cell_coercion_str(self):
        t = Table(["n", "v"])
        t.add_row(42, None)
        self.assertEqual(
            t.render(),
            "+----+------+\n| n  | v    |\n+----+------+\n| 42 | None |\n+----+------+",
        )

    def test_empty_string_cell(self):
        t = Table(["a", "b"])
        t.add_row("", "")
        self.assertIn("|   |   |", t.render())

    def test_pipe_not_escaped(self):
        t = Table(["v"])
        t.add_row("a|b")
        self.assertIn("| a|b |", t.render())

    def test_cjk_width_is_one(self):
        # 历史口径：宽度按 len() 算，中文按 1 个宽（边框对不齐就随它去）
        t = Table(["指标"])
        t.add_row("值")
        self.assertEqual(
            t.render(), "+----+\n| 指标 |\n+----+\n| 值  |\n+----+"
        )

    def test_leading_trailing_spaces_kept(self):
        t = Table(["h"])
        t.add_row("  spaced  ")
        self.assertEqual(
            t.render(),
            "+------------+\n| h          |\n+------------+\n|   spaced   |\n+------------+",
        )

    def test_headers_coerced_str(self):
        t = Table([1, 2])
        self.assertEqual(t.render(), "+---+---+\n| 1 | 2 |\n+---+---+")

    def test_render_twice_identical(self):
        t = Table(["a", "b"])
        t.add_row("1", "2")
        self.assertEqual(t.render(), t.render())

    def test_add_after_render(self):
        t = Table(["a"])
        t.add_row("1")
        before = t.render()
        t.add_row("22")
        after = t.render()
        self.assertNotEqual(before, after)
        self.assertEqual(after, "+----+\n| a  |\n+----+\n| 1  |\n| 22 |\n+----+")


class TestWrap(unittest.TestCase):
    def test_wrap_zero_single_line(self):
        t = Table(["h"], wrap=0)
        t.add_row("aaaa bbbb cccc")
        self.assertEqual(
            t.render(),
            "+----------------+\n"
            "| h              |\n"
            "+----------------+\n"
            "| aaaa bbbb cccc |\n"
            "+----------------+",
        )

    def test_wrap_greedy_words(self):
        t = Table(["h"], wrap=6)
        t.add_row("the quick brown")
        self.assertEqual(
            t.render(),
            "+-------+\n| h     |\n+-------+\n| the   |\n| quick |\n| brown |\n+-------+",
        )

    def test_wrap_long_word_hard_split(self):
        t = Table(["h"], wrap=4)
        t.add_row("abcdefgh")
        self.assertEqual(
            t.render(),
            "+------+\n| h    |\n+------+\n| abcd |\n| efgh |\n+------+",
        )
        t2 = Table(["h"], wrap=4)
        t2.add_row("abcde")
        self.assertEqual(
            t2.render(),
            "+------+\n| h    |\n+------+\n| abcd |\n| e    |\n+------+",
        )

    def test_wrap_exact_fit_new_line(self):
        t = Table(["h"], wrap=4)
        t.add_row("abcd efgh")
        self.assertEqual(
            t.render(),
            "+------+\n| h    |\n+------+\n| abcd |\n| efgh |\n+------+",
        )

    def test_wrap_empty_cell_one_blank_line(self):
        t = Table(["h"], wrap=4)
        t.add_row("")
        self.assertEqual(t.render(), "+---+\n| h |\n+---+\n|   |\n+---+")

    def test_wrap_header_hard_split(self):
        # 词超过 wrap 先清行再硬切的历史行为：words 被切成 word + s
        t = Table(["two words"], wrap=4)
        self.assertEqual(
            t.render(), "+------+\n| two  |\n| word |\n| s    |\n+------+"
        )

    def test_wrap_row_heights_differ(self):
        t = Table(["m", "note"], wrap=6)
        t.add_row("x", "alpha beta gamma")
        self.assertEqual(
            t.render(),
            "+---+-------+\n"
            "| m | note  |\n"
            "+---+-------+\n"
            "| x | alpha |\n"
            "|   | beta  |\n"
            "|   | gamma |\n"
            "+---+-------+",
        )

    def test_wrap_multiple_spaces_collapsed(self):
        t = Table(["h"], wrap=4)
        t.add_row("a    b")
        self.assertIn("| a b |", t.render())
        t2 = Table(["h"], wrap=0)
        t2.add_row("a    b")
        self.assertIn("| a    b |", t2.render())


if __name__ == "__main__":
    unittest.main()
