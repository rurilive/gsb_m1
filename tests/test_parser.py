import unittest

from jsonflow import JsonError, Num, loads


class DocumentShapeTest(unittest.TestCase):
    def test_scalars(self):
        self.assertEqual(loads('"text"'), "text")
        self.assertIs(loads("true"), True)
        self.assertIs(loads("false"), False)
        self.assertIsNone(loads("null"))

    def test_nested_shape(self):
        doc = loads('{"a": [1, [2.5, "x"]], "b": {"c": null}}')
        self.assertEqual(sorted(doc), ["a", "b"])
        self.assertEqual(len(doc["a"]), 2)
        self.assertEqual(doc["a"][1][1], "x")
        self.assertIsNone(doc["b"]["c"])

    def test_empty_containers(self):
        self.assertEqual(loads("{}"), {})
        self.assertEqual(loads("[]"), [])
        self.assertEqual(loads(" [ { } , [ ] ] "), [{}, []])

    def test_surrounding_whitespace(self):
        self.assertEqual(loads('\n\t {"k": "v"} \n'), {"k": "v"})

    def test_bytes_input(self):
        self.assertEqual(loads(b'{"k": "v"}'), {"k": "v"})


class NumberShapeTest(unittest.TestCase):
    def test_numbers_are_wrapped(self):
        doc = loads('{"a": 7, "b": 2.5}')
        self.assertIsInstance(doc["a"], Num)
        self.assertIsInstance(doc["b"], Num)

    def test_literal_text_is_kept(self):
        doc = loads('{"a": 7, "b": -1.25e+3}')
        self.assertEqual(doc["a"].text, "7")
        self.assertEqual(doc["b"].text, "-1.25e+3")

    def test_value_is_usable_as_python_number(self):
        doc = loads('{"a": 7, "b": 2.5}')
        self.assertEqual(doc["a"].value, 7)
        self.assertEqual(float(doc["b"]), 2.5)
        self.assertEqual(int(doc["a"]), 7)

    def test_same_literal_compares_equal(self):
        self.assertEqual(loads("42"), loads("42"))
        self.assertNotEqual(loads("42"), loads("43"))


class FailureTest(unittest.TestCase):
    def test_trailing_content(self):
        with self.assertRaises(JsonError):
            loads('{"a": 1} extra')

    def test_unclosed_object(self):
        with self.assertRaises(JsonError):
            loads('{"a": 1')

    def test_missing_colon(self):
        with self.assertRaises(JsonError):
            loads('{"a" 1}')

    def test_empty_input(self):
        with self.assertRaises(JsonError):
            loads("")


if __name__ == "__main__":
    unittest.main()
