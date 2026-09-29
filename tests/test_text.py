"""Baseline behaviour tests for FlatText.

This file pins the current flat buffer semantics. It must stay unchanged and
keep passing as the library evolves.
"""

import unittest

from ropetex import FlatText


class FlatTextBasicsTest(unittest.TestCase):
    def test_empty_initial(self):
        t = FlatText()
        self.assertEqual(len(t), 0)
        self.assertEqual(t.toString(), "")

    def test_initial_value(self):
        t = FlatText("hello")
        self.assertEqual(t.length, 5)
        self.assertEqual(t.toString(), "hello")

    def test_initial_must_be_str(self):
        with self.assertRaises(TypeError):
            FlatText(123)

    def test_len_and_length_agree(self):
        t = FlatText("abcdef")
        self.assertEqual(len(t), t.length)


class FlatTextCharAtTest(unittest.TestCase):
    def test_char_at_in_range(self):
        t = FlatText("abcdef")
        self.assertEqual(t.charAt(0), "a")
        self.assertEqual(t.charAt(5), "f")

    def test_char_at_out_of_range_returns_empty(self):
        t = FlatText("abc")
        self.assertEqual(t.charAt(3), "")
        self.assertEqual(t.charAt(99), "")

    def test_char_at_negative_returns_empty(self):
        t = FlatText("abc")
        self.assertEqual(t.charAt(-1), "")


class FlatTextSubstringTest(unittest.TestCase):
    def test_substring_plain(self):
        t = FlatText("abcdef")
        self.assertEqual(t.substring(1, 4), "bcd")

    def test_substring_clamps_end(self):
        t = FlatText("abcdef")
        self.assertEqual(t.substring(3, 100), "def")

    def test_substring_clamps_start(self):
        t = FlatText("abcdef")
        self.assertEqual(t.substring(-5, 2), "ab")

    def test_substring_empty_when_start_ge_end(self):
        t = FlatText("abcdef")
        self.assertEqual(t.substring(4, 4), "")
        self.assertEqual(t.substring(5, 2), "")


class FlatTextInsertDeleteTest(unittest.TestCase):
    def test_insert_middle(self):
        t = FlatText("abd")
        new_len = t.insert(2, "c")
        self.assertEqual(new_len, 4)
        self.assertEqual(t.toString(), "abcd")

    def test_insert_append_at_end(self):
        t = FlatText("abc")
        t.insert(3, "def")
        self.assertEqual(t.toString(), "abcdef")

    def test_insert_at_zero(self):
        t = FlatText("world")
        t.insert(0, "hello ")
        self.assertEqual(t.toString(), "hello world")

    def test_insert_out_of_range(self):
        t = FlatText("abc")
        with self.assertRaises(ValueError):
            t.insert(4, "x")
        with self.assertRaises(ValueError):
            t.insert(-1, "x")

    def test_insert_non_str(self):
        t = FlatText("abc")
        with self.assertRaises(TypeError):
            t.insert(1, 5)

    def test_delete_middle(self):
        t = FlatText("abcdef")
        removed = t.delete(2, 4)
        self.assertEqual(removed, 2)
        self.assertEqual(t.toString(), "abef")

    def test_delete_to_end(self):
        t = FlatText("abcdef")
        t.delete(3, 6)
        self.assertEqual(t.toString(), "abc")

    def test_delete_empty_range_is_noop(self):
        t = FlatText("abc")
        removed = t.delete(1, 1)
        self.assertEqual(removed, 0)
        self.assertEqual(t.toString(), "abc")

    def test_delete_out_of_range(self):
        t = FlatText("abc")
        with self.assertRaises(ValueError):
            t.delete(2, 10)
        with self.assertRaises(ValueError):
            t.delete(-1, 2)
        with self.assertRaises(ValueError):
            t.delete(2, 1)

    def test_delete_all(self):
        t = FlatText("abc")
        t.delete(0, 3)
        self.assertEqual(t.toString(), "")
        self.assertEqual(len(t), 0)


class FlatTextReprTest(unittest.TestCase):
    def test_str_matches_to_string(self):
        t = FlatText("xyz")
        self.assertEqual(str(t), t.toString())

    def test_repr_mentions_class(self):
        t = FlatText("xyz")
        self.assertIn("FlatText", repr(t))


if __name__ == "__main__":
    unittest.main()
