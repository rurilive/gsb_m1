"""parse_range / match / best 的行为测试。"""

import unittest

from verkit.range import best, match, parse_range
from verkit.version import parse_version


class TestCaret(unittest.TestCase):
    def test_caret_basic(self):
        r = "^1.2.3"
        self.assertTrue(match("1.2.3", r))
        self.assertTrue(match("1.9.0", r))
        self.assertFalse(match("2.0.0", r))
        self.assertFalse(match("1.2.2", r))

    def test_caret_zero_major(self):
        r = "^0.2.3"
        self.assertTrue(match("0.2.3", r))
        self.assertTrue(match("0.2.9", r))
        self.assertFalse(match("0.3.0", r))
        self.assertFalse(match("1.0.0", r))

    def test_caret_zero_zero(self):
        r = "^0.0.3"
        self.assertTrue(match("0.0.3", r))
        self.assertFalse(match("0.0.4", r))
        self.assertFalse(match("0.1.0", r))

    def test_caret_missing_segments(self):
        self.assertTrue(match("1.2.0", "^1.2"))
        self.assertTrue(match("1.9.9", "^1.2"))
        self.assertFalse(match("1.1.9", "^1.2"))
        self.assertFalse(match("2.0.0", "^1.2"))
        self.assertTrue(match("1.9.9", "^1"))
        self.assertFalse(match("2.0.0", "^1"))

    def test_caret_zero_missing_segments(self):
        self.assertTrue(match("0.0.5", "^0.0"))
        self.assertFalse(match("0.1.0", "^0.0"))
        self.assertTrue(match("0.9.9", "^0"))
        self.assertFalse(match("1.0.0", "^0"))

    def test_caret_all_zero(self):
        self.assertTrue(match("0.0.0", "^0.0.0"))
        self.assertFalse(match("0.0.1", "^0.0.0"))


class TestTilde(unittest.TestCase):
    def test_tilde_full(self):
        r = "~1.2.3"
        self.assertTrue(match("1.2.3", r))
        self.assertTrue(match("1.2.9", r))
        self.assertFalse(match("1.3.0", r))
        self.assertFalse(match("1.2.2", r))

    def test_tilde_missing_patch(self):
        self.assertTrue(match("1.2.0", "~1.2"))
        self.assertTrue(match("1.2.9", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))

    def test_tilde_major_only(self):
        self.assertTrue(match("1.9.9", "~1"))
        self.assertFalse(match("2.0.0", "~1"))

    def test_tilde_zero_major(self):
        self.assertTrue(match("0.2.9", "~0.2.3"))
        self.assertFalse(match("0.3.0", "~0.2.3"))


class TestBasicComparators(unittest.TestCase):
    def test_and_of_space_separated(self):
        r = ">=1.2.0 <1.3.0"
        self.assertTrue(match("1.2.0", r))
        self.assertTrue(match("1.2.9", r))
        self.assertFalse(match("1.3.0", r))
        self.assertFalse(match("1.1.9", r))

    def test_missing_segments_fill_zero(self):
        self.assertTrue(match("1.2.0", ">=1.2"))
        self.assertFalse(match("1.1.9", ">=1.2"))
        self.assertTrue(match("1.2.0", "1.2"))
        self.assertFalse(match("1.2.1", "1.2"))

    def test_exclusive_bounds(self):
        self.assertFalse(match("1.2.3", ">1.2.3"))
        self.assertTrue(match("1.2.4", ">1.2.3"))
        self.assertFalse(match("1.2.3", "<1.2.3"))
        self.assertTrue(match("1.2.2", "<1.2.3"))
        self.assertTrue(match("1.2.3", "<=1.2.3"))

    def test_exact_and_build_metadata(self):
        self.assertTrue(match("1.2.3", "=1.2.3"))
        self.assertTrue(match("1.2.3+build.5", "=1.2.3"))
        self.assertFalse(match("1.2.4", "=1.2.3"))

    def test_not_equal(self):
        r = ">=1.0.0 !=1.2.3"
        self.assertFalse(match("1.2.3", r))
        self.assertFalse(match("1.2.3+build.1", r))
        self.assertTrue(match("1.2.4", r))
        self.assertFalse(match("0.9.9", r))

    def test_not_equal_prerelease(self):
        r = "!=1.2.3-beta"
        self.assertFalse(match("1.2.3-beta", r))
        self.assertTrue(match("1.2.3", r))


class TestWildcard(unittest.TestCase):
    def test_minor_wildcard(self):
        r = "1.x"
        self.assertTrue(match("1.0.0", r))
        self.assertTrue(match("1.9.9", r))
        self.assertFalse(match("2.0.0", r))
        self.assertFalse(match("0.9.9", r))

    def test_patch_wildcard(self):
        r = "1.2.x"
        self.assertTrue(match("1.2.0", r))
        self.assertTrue(match("1.2.9", r))
        self.assertFalse(match("1.3.0", r))

    def test_star_and_empty(self):
        self.assertTrue(match("0.0.0", "*"))
        self.assertTrue(match("9.9.9", "*"))
        self.assertTrue(match("3.1.4", ""))

    def test_wildcard_with_equals(self):
        self.assertTrue(match("1.2.5", "=1.2.x"))
        self.assertFalse(match("1.3.0", "=1.2.x"))


class TestOr(unittest.TestCase):
    def test_or_branches(self):
        r = "^1.2.0 || >=2.0.0"
        self.assertTrue(match("1.5.0", r))
        self.assertTrue(match("2.0.0", r))
        self.assertTrue(match("3.1.0", r))
        self.assertFalse(match("1.1.0", r))

    def test_or_with_and_inside(self):
        r = ">=1.0.0 <1.5.0 || >=2.0.0 <2.5.0"
        self.assertTrue(match("1.4.9", r))
        self.assertTrue(match("2.4.9", r))
        self.assertFalse(match("1.5.0", r))
        self.assertFalse(match("2.5.0", r))


class TestPrerelease(unittest.TestCase):
    def test_prerelease_excluded_by_default(self):
        self.assertFalse(match("1.5.0-rc.1", "^1.0.0"))
        self.assertFalse(match("2.0.0-rc.1", ">=1.0.0"))
        self.assertFalse(match("1.0.0-alpha", "*"))

    def test_prerelease_allowed_same_tuple(self):
        r = "^1.2.3-beta.1"
        self.assertTrue(match("1.2.3-beta.1", r))
        self.assertTrue(match("1.2.3-beta.2", r))
        self.assertTrue(match("1.2.3", r))
        self.assertTrue(match("1.5.0", r))

    def test_prerelease_other_tuple_still_excluded(self):
        r = "^1.2.3-beta.1"
        self.assertFalse(match("1.2.4-alpha", r))
        self.assertFalse(match("1.2.2-beta.1", r))

    def test_prerelease_gate_is_per_or_branch(self):
        r = "^1.2.3-beta.1 || ^2.0.0"
        self.assertTrue(match("1.2.3-beta.5", r))
        self.assertFalse(match("2.5.0-rc.1", r))
        self.assertTrue(match("2.5.0", r))

    def test_prerelease_lower_bound_chain(self):
        r = ">1.0.0-alpha"
        self.assertTrue(match("1.0.0-beta", r))
        self.assertTrue(match("1.0.0", r))
        self.assertTrue(match("1.0.1", r))
        self.assertFalse(match("1.0.0-alpha", r))
        self.assertFalse(match("2.0.0-alpha", r))

    def test_release_always_matches(self):
        self.assertTrue(match("1.2.3", "^1.2.3-rc.1"))


class TestBest(unittest.TestCase):
    def test_best_picks_highest(self):
        got = best(["1.2.3", "1.4.0", "2.0.0", "1.4.0-beta.1"], "^1.0.0")
        self.assertEqual(str(got), "1.4.0")

    def test_best_none_when_empty(self):
        self.assertIsNone(best(["0.9.0", "2.0.0"], "^1.0.0"))
        self.assertIsNone(best([], "*"))

    def test_best_with_prerelease_allowed(self):
        got = best(["1.2.3-beta.1", "1.2.3-beta.2", "1.2.2"], "^1.2.3-beta.1")
        self.assertEqual(str(got), "1.2.3-beta.2")

    def test_best_accepts_version_objects(self):
        got = best([parse_version("1.0.0"), parse_version("1.1.0")], "^1.0.0")
        self.assertEqual(got, parse_version("1.1.0"))

    def test_best_zero_caret(self):
        got = best(["0.2.3", "0.2.9", "0.3.0"], "^0.2.3")
        self.assertEqual(str(got), "0.2.9")


class TestParseErrors(unittest.TestCase):
    def test_reject_garbage(self):
        for bad in ("^", "~", ">=", "1.2.3.4", "foo", "1.x.2", "!=1.x",
                    ">1.x", "1.2.3 ||", "|| 1.2.3", "1.2.3-", "v1.2.3"):
            with self.assertRaises(ValueError, msg=bad):
                parse_range(bad)

    def test_reject_non_string(self):
        with self.assertRaises(ValueError):
            parse_range(123)

    def test_parse_range_idempotent(self):
        r = parse_range("^1.2.3")
        self.assertIs(parse_range(r), r)
        self.assertTrue(match("1.5.0", r))


if __name__ == "__main__":
    unittest.main()
