import unittest

from jsonflow import dumps, loads


class DumpShapeTest(unittest.TestCase):
    def test_scalars(self):
        self.assertEqual(dumps(None), "null")
        self.assertEqual(dumps(True), "true")
        self.assertEqual(dumps("x"), '"x"')
        self.assertEqual(dumps(7), "7")
        self.assertEqual(dumps(1.5), "1.5")

    def test_containers_use_standard_separators(self):
        self.assertEqual(dumps([1, 2.5, None]), "[1, 2.5, null]")
        self.assertEqual(dumps({"a": 1, "b": [True, "x"]}), '{"a": 1, "b": [true, "x"]}')

    def test_string_escaping(self):
        self.assertEqual(dumps({"s": 'a"b\nc'}), '{"s": "a\\"b\\nc"}')
        self.assertEqual(dumps({"s": "é"}), '{"s": "\\u00e9"}')

    def test_empty_containers(self):
        self.assertEqual(dumps({}), "{}")
        self.assertEqual(dumps([]), "[]")

    def test_negative_zero_float_is_signed(self):
        self.assertEqual(dumps({"v": -0.0}), '{"v": -0.0}')
        self.assertEqual(dumps({"v": 0.0}), '{"v": 0.0}')

    def test_rejects_bad_types(self):
        with self.assertRaises(TypeError):
            dumps({1: "x"})
        with self.assertRaises(TypeError):
            dumps(object())


class RoundTripTest(unittest.TestCase):
    def test_dumps_of_parsed_document(self):
        text = '{"name": "x", "flag": true, "n": null, "list": [1, 2.5]}'
        self.assertEqual(dumps(loads(text)), text)

    def test_dumps_of_negative_integer(self):
        self.assertEqual(dumps(loads("-3")), "-3")

    def test_round_trip_into_parsed_again(self):
        text = '{"a": [1, 2.5], "b": "s"}'
        once = dumps(loads(text))
        self.assertEqual(dumps(loads(once)), once)


if __name__ == "__main__":
    unittest.main()
