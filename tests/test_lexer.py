import unittest

from jsonflow import JsonError, Lexer


def tokenize(text):
    lexer = Lexer(text)
    tokens = []
    while True:
        token = lexer.next_token()
        tokens.append(token)
        if token.kind == "EOF":
            return tokens


class TokenStreamTest(unittest.TestCase):
    def test_document_tokens(self):
        tokens = tokenize('{"a": [1, true], "b": null}')
        kinds = [token.kind for token in tokens]
        self.assertEqual(
            kinds,
            [
                "LBRACE",
                "STRING",
                "COLON",
                "LBRACKET",
                "NUMBER",
                "COMMA",
                "TRUE",
                "RBRACKET",
                "COMMA",
                "STRING",
                "COLON",
                "NULL",
                "RBRACE",
                "EOF",
            ],
        )

    def test_string_token_is_decoded(self):
        tokens = tokenize('"line\\n\\u00e9"')
        self.assertEqual(tokens[0].kind, "STRING")
        self.assertEqual(tokens[0].value, "line\né")

    def test_number_token_keeps_raw_text(self):
        tokens = tokenize("[ -1.25e+3 , 0.5 ]")
        self.assertEqual(tokens[1].value, "-1.25e+3")
        self.assertEqual(tokens[3].value, "0.5")

    def test_positions(self):
        tokens = tokenize('{\n  "a": 1\n}')
        string_token = tokens[1]
        self.assertEqual((string_token.pos, string_token.line, string_token.col), (4, 2, 3))
        number_token = tokens[3]
        self.assertEqual((number_token.pos, number_token.line, number_token.col), (9, 2, 8))
        brace_token = tokens[4]
        self.assertEqual((brace_token.line, brace_token.col), (3, 1))

    def test_unterminated_string(self):
        with self.assertRaises(JsonError):
            tokenize('"abc')

    def test_unknown_character(self):
        with self.assertRaises(JsonError):
            tokenize("[1, @]")


if __name__ == "__main__":
    unittest.main()
