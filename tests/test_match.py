"""match(pattern, path) 现有行为的锁定测试。"""

import unittest

from pathmatch.match import match


class TestSegmentGlob(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(match("build.log", "build.log"))
        self.assertFalse(match("build.log", "dist/build.log"))

    def test_star_within_segment(self):
        self.assertTrue(match("*.py", "main.py"))
        self.assertFalse(match("*.py", "src/main.py"))

    def test_star_does_not_cross_segments(self):
        self.assertTrue(match("src/*.py", "src/main.py"))
        self.assertFalse(match("src/*.py", "src/pkg/main.py"))

    def test_segment_count_must_align(self):
        self.assertFalse(match("a/c", "a/b/c"))
        self.assertFalse(match("a/b/c", "a/c"))

    def test_star_matches_empty_remainder(self):
        self.assertTrue(match("a/*", "a/"))
        self.assertTrue(match("a*", "abc"))

    def test_question_mark(self):
        self.assertTrue(match("a?c", "abc"))
        self.assertFalse(match("a?c", "ac"))
        self.assertFalse(match("a?c", "abbc"))

    def test_middle_star_single_segment(self):
        self.assertTrue(match("src/*/init.py", "src/core/init.py"))
        self.assertFalse(match("src/*/init.py", "src/core/sub/init.py"))

    def test_case_sensitive(self):
        self.assertFalse(match("*.PY", "main.py"))
        self.assertFalse(match("Readme*", "readme.md"))

    def test_regex_chars_are_literal(self):
        self.assertTrue(match("a+b.txt", "a+b.txt"))
        self.assertFalse(match("a+b.txt", "aab.txt"))
        self.assertFalse(match("a.txt", "axtxt"))

    def test_multi_segment_pattern(self):
        self.assertTrue(match("a/*/d", "a/b/d"))
        self.assertTrue(match("a/*", "a/bc"))
        self.assertFalse(match("a/*", "a/b/c"))

    def test_star_in_every_segment(self):
        self.assertTrue(match("*/*", "x/y"))
        self.assertFalse(match("*/*", "x/y/z"))


if __name__ == "__main__":
    unittest.main()
