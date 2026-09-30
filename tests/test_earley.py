"""Grammar 与 BacktrackParser 现有行为的锁定测试（基线，一字不改）。

基线是回溯递归下降，遇到左递归文法会陷进无限递归，因此这里的文法一律避开
左递归，只锁住现有能正确处理的这一类行为。
"""

import unittest

from parsex.earley import (
    BacktrackParser,
    Grammar,
    GrammarError,
    InvalidInputError,
    ParseNode,
    ParsexError,
)

# 右递归的四则表达式文法：E -> T+E | T ; T -> F*T | F ; F -> (E) | a
ARITH = Grammar([
    ("E", "T+E"),
    ("E", "T"),
    ("T", "F*T"),
    ("T", "F"),
    ("F", "(E)"),
    ("F", "a"),
])

# 非左递归的歧义文法：S -> aSb | ab | 空
AMBIG = Grammar([
    ("S", "aSb"),
    ("S", "ab"),
    ("S", ""),
])

# 带空产生式的括号配对文法：S -> aSb | 空
BALANCED = Grammar([
    ("S", "aSb"),
    ("S", ""),
])


class TestGrammar(unittest.TestCase):
    def test_start_symbol(self):
        self.assertEqual(ARITH.start(), "E")

    def test_nonterminals(self):
        self.assertEqual(ARITH.nonterminals(), ("E", "T", "F"))

    def test_terminals(self):
        self.assertEqual(ARITH.terminals(), ("+", "*", "(", ")", "a"))

    def test_rules_preserved(self):
        self.assertEqual(ARITH.rules()[0], ("E", "T+E"))

    def test_rules_for(self):
        self.assertEqual(ARITH.rules_for("F"), ("(E)", "a"))

    def test_empty_rhs_allowed(self):
        self.assertIn("", BALANCED.rules_for("S"))

    def test_rule_shape_rejected(self):
        with self.assertRaises(GrammarError):
            Grammar([("A",)])

    def test_lhs_not_single_char_rejected(self):
        with self.assertRaises(GrammarError):
            Grammar([("AB", "a")])

    def test_rhs_not_string_rejected(self):
        with self.assertRaises(GrammarError):
            Grammar([("A", 1)])

    def test_empty_grammar_rejected(self):
        with self.assertRaises(GrammarError):
            Grammar([])


class TestAccept(unittest.TestCase):
    def test_accept_single_letter(self):
        self.assertTrue(BacktrackParser(ARITH).accepts("a"))

    def test_accept_simple_expression(self):
        self.assertTrue(BacktrackParser(ARITH).accepts("a+a"))

    def test_accept_nested(self):
        self.assertTrue(BacktrackParser(ARITH).accepts("(a+a)*a"))

    def test_reject_missing_operand(self):
        self.assertFalse(BacktrackParser(ARITH).accepts("a+"))

    def test_reject_bad_parenthesis(self):
        self.assertFalse(BacktrackParser(ARITH).accepts("(a"))

    def test_reject_foreign_symbol(self):
        self.assertFalse(BacktrackParser(ARITH).accepts("b"))

    def test_accept_empty_string(self):
        self.assertTrue(BacktrackParser(BALANCED).accepts(""))

    def test_reject_empty_string(self):
        self.assertFalse(BacktrackParser(ARITH).accepts(""))


class TestParseTree(unittest.TestCase):
    def test_parse_lowest_derivation(self):
        self.assertEqual(
            BacktrackParser(ARITH).parse("a"),
            ParseNode("E", [ParseNode("T", [ParseNode("F", [ParseNode("a")])])]),
        )

    def test_parse_unrecognized_is_none(self):
        self.assertIsNone(BacktrackParser(ARITH).parse("+"))

    def test_parse_null_production_grammar(self):
        self.assertTrue(BacktrackParser(BALANCED).accepts("aabb"))
        self.assertTrue(BacktrackParser(BALANCED).accepts(""))
        self.assertEqual(
            BacktrackParser(BALANCED).parse("ab"),
            ParseNode("S", [ParseNode("a"), ParseNode("S", []), ParseNode("b")]),
        )

    def test_parse_returns_expected_root(self):
        node = BacktrackParser(AMBIG).parse("ab")
        self.assertEqual(node.symbol, "S")


class TestEnumerateParses(unittest.TestCase):
    def test_all_parses_single_letter(self):
        parses = BacktrackParser(ARITH).all_parses("a")
        self.assertEqual(len(parses), 1)

    def test_all_parses_ambiguous(self):
        parses = BacktrackParser(AMBIG).all_parses("ab")
        self.assertEqual(len(parses), 2)

    def test_all_parses_unrecognized_empty(self):
        self.assertEqual(BacktrackParser(ARITH).all_parses("+"), ())

    def test_count_parses(self):
        self.assertEqual(BacktrackParser(AMBIG).count_parses("aabb"), 2)

    def test_count_parses_matches_all(self):
        parser = BacktrackParser(AMBIG)
        self.assertEqual(len(parser.all_parses("ab")), parser.count_parses("ab"))

    def test_every_parse_is_derived(self):
        for node in BacktrackParser(AMBIG).all_parses("ab"):
            self.assertEqual(node.symbol, "S")


class TestMatches(unittest.TestCase):
    def test_matches_balanced_spans(self):
        spans = BacktrackParser(BALANCED).matches("S", "aabb")
        self.assertEqual(
            spans,
            ((0, 0), (0, 4), (1, 1), (1, 3), (2, 2), (3, 3), (4, 4)),
        )

    def test_matches_single_terminal_rule(self):
        spans = BacktrackParser(ARITH).matches("F", "a")
        self.assertEqual(spans, ((0, 1),))

    def test_matches_empty_production_positions(self):
        grammar = Grammar([("S", ""), ("S", "a")])
        spans = BacktrackParser(grammar).matches("S", "aa")
        self.assertEqual(spans, ((0, 0), (0, 1), (1, 1), (1, 2), (2, 2)))

    def test_matches_unknown_nonterminal_rejected(self):
        with self.assertRaises(InvalidInputError):
            BacktrackParser(ARITH).matches("Z", "a")

    def test_attempts_counted(self):
        parser = BacktrackParser(ARITH)
        parser.accepts("a+a")
        self.assertGreater(parser.attempts(), 0)


class TestErrors(unittest.TestCase):
    def test_non_string_text_rejected(self):
        with self.assertRaises(InvalidInputError):
            BacktrackParser(ARITH).accepts(123)

    def test_non_string_matches_text_rejected(self):
        with self.assertRaises(InvalidInputError):
            BacktrackParser(ARITH).matches("F", 1.5)

    def test_parser_needs_grammar(self):
        with self.assertRaises(InvalidInputError):
            BacktrackParser(["S", "a"])

    def test_grammar_error_base_class(self):
        self.assertTrue(issubclass(GrammarError, ParsexError))

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidInputError, ParsexError))
        self.assertTrue(issubclass(ParsexError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_accepts_repeat_same(self):
        parser = BacktrackParser(ARITH)
        self.assertEqual(parser.accepts("(a+a)*a"), parser.accepts("(a+a)*a"))

    def test_all_parses_repeat_same(self):
        parser = BacktrackParser(AMBIG)
        self.assertEqual(parser.all_parses("ab"), parser.all_parses("ab"))

    def test_matches_repeat_same(self):
        parser = BacktrackParser(BALANCED)
        self.assertEqual(parser.matches("S", "ab"), parser.matches("S", "ab"))


if __name__ == "__main__":
    unittest.main()
