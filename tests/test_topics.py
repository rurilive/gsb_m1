"""主题切分与模式匹配的锁定测试。"""

import unittest

from eventwire.topics import matches, split_pattern, split_topic


class TestSplitTopic(unittest.TestCase):
    def test_segments_in_order(self):
        self.assertEqual(split_topic("gateway.retry.done"),
                         ("gateway", "retry", "done"))

    def test_single_segment(self):
        self.assertEqual(split_topic("tick"), ("tick",))

    def test_empty_segments_rejected(self):
        for bad in ["", "a..b", ".a", "a.", "."]:
            with self.assertRaises(ValueError):
                split_topic(bad)

    def test_wildcard_segments_rejected_in_topic(self):
        for bad in ["a.*", "*.a", "a.**", "**"]:
            with self.assertRaises(ValueError):
                split_topic(bad)

    def test_non_str_rejected(self):
        with self.assertRaises(TypeError):
            split_topic(3)


class TestSplitPattern(unittest.TestCase):
    def test_plain_pattern(self):
        self.assertEqual(split_pattern("a.b"), ("a", "b"))

    def test_star_anywhere(self):
        self.assertEqual(split_pattern("a.*.c"), ("a", "*", "c"))

    def test_double_star_at_end_only(self):
        self.assertEqual(split_pattern("a.**"), ("a", "**"))
        self.assertEqual(split_pattern("**"), ("**",))
        with self.assertRaises(ValueError):
            split_pattern("a.**.b")

    def test_half_wildcard_segment_rejected(self):
        for bad in ["a*b", "a.**b", "**x"]:
            with self.assertRaises(ValueError):
                split_pattern(bad)

    def test_empty_segment_rejected(self):
        for bad in ["", "a..b", ".a"]:
            with self.assertRaises(ValueError):
                split_pattern(bad)


class TestMatches(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(matches("a.b", "a.b"))
        self.assertFalse(matches("a.b", "a.c"))
        self.assertFalse(matches("a.b", "a.b.c"))
        self.assertFalse(matches("a.b.c", "a.b"))

    def test_star_covers_exactly_one_segment(self):
        self.assertTrue(matches("a.*", "a.b"))
        self.assertFalse(matches("a.*", "a.b.c"))
        self.assertFalse(matches("a.*", "a"))

    def test_double_star_covers_zero_segments(self):
        self.assertTrue(matches("a.**", "a"))

    def test_double_star_covers_many_segments(self):
        self.assertTrue(matches("a.**", "a.b.c.d"))

    def test_bare_double_star_matches_everything(self):
        self.assertTrue(matches("**", "a"))
        self.assertTrue(matches("**", "a.b.c"))

    def test_match_is_case_sensitive(self):
        self.assertFalse(matches("a.B", "a.b"))


if __name__ == "__main__":
    unittest.main()
