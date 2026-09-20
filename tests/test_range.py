"""parse_range / match / best 的行为测试。"""

import unittest

from verkit.range import Range, best, match, parse_range
from verkit.version import parse_version


class TestParseRange(unittest.TestCase):
    def test_returns_range_object(self):
        self.assertIsInstance(parse_range("^1.2.3"), Range)

    def test_passthrough_range_object(self):
        r = parse_range("1.2.3")
        self.assertIs(parse_range(r), r)

    def test_empty_and_star_match_any_release(self):
        for spec in ("", "  ", "*", "x"):
            self.assertTrue(match("1.2.3", spec), spec)
            self.assertTrue(match("0.0.1", spec), spec)

    def test_reject_garbage(self):
        for spec in ("=>1.2.3", "1.2.3.4", "^", "~", "abc", "1.2.3-", ">=", "!=1.x"):
            with self.assertRaises(ValueError, msg=spec):
                parse_range(spec)

    def test_reject_non_string(self):
        with self.assertRaises(ValueError):
            parse_range(123)


class TestPlainComparators(unittest.TestCase):
    def test_bare_version_is_exact(self):
        self.assertTrue(match("1.2.3", "1.2.3"))
        self.assertFalse(match("1.2.4", "1.2.3"))

    def test_missing_segments_fill_zero(self):
        self.assertTrue(match("1.2.0", "1.2"))
        self.assertFalse(match("1.2.5", "1.2"))
        self.assertTrue(match("1.0.0", "=1"))
        self.assertTrue(match("1.2.0", ">=1.2"))
        self.assertFalse(match("1.1.9", ">=1.2"))

    def test_space_is_and(self):
        self.assertTrue(match("1.5.0", ">=1.2.0 <2.0.0"))
        self.assertFalse(match("2.0.0", ">=1.2.0 <2.0.0"))
        self.assertFalse(match("1.1.9", ">=1.2.0 <2.0.0"))

    def test_or_branches(self):
        spec = "<1.0.0 || >=2.0.0"
        self.assertTrue(match("0.9.9", spec))
        self.assertTrue(match("2.0.0", spec))
        self.assertFalse(match("1.5.0", spec))

    def test_not_equal_excludes_exactly(self):
        spec = ">=1.0.0 <2.0.0 !=1.5.0"
        self.assertTrue(match("1.4.9", spec))
        self.assertTrue(match("1.5.1", spec))
        self.assertFalse(match("1.5.0", spec))

    def test_boundary_ops(self):
        self.assertTrue(match("1.2.3", "<=1.2.3"))
        self.assertFalse(match("1.2.3", "<1.2.3"))
        self.assertTrue(match("1.2.3", ">=1.2.3"))
        self.assertFalse(match("1.2.3", ">1.2.3"))

    def test_build_metadata_ignored(self):
        self.assertTrue(match("1.2.3+build.7", "=1.2.3"))
        self.assertTrue(match("1.2.3", "=1.2.3+build.7"))


class TestWildcard(unittest.TestCase):
    def test_major_wildcard(self):
        self.assertTrue(match("1.9.9", "1.x"))
        self.assertFalse(match("2.0.0", "1.x"))

    def test_minor_wildcard(self):
        self.assertTrue(match("1.2.0", "1.2.x"))
        self.assertTrue(match("1.2.99", "1.2.*"))
        self.assertFalse(match("1.3.0", "1.2.x"))

    def test_wildcard_with_inequality_fills_zero(self):
        self.assertTrue(match("1.2.0", ">=1.2.x"))
        self.assertFalse(match("1.1.9", ">=1.2.x"))

    def test_wildcard_rejects_prerelease_combo(self):
        with self.assertRaises(ValueError):
            parse_range("1.2.x-beta")


class TestCaret(unittest.TestCase):
    def test_basic(self):
        self.assertTrue(match("1.2.3", "^1.2.3"))
        self.assertTrue(match("1.9.0", "^1.2.3"))
        self.assertFalse(match("2.0.0", "^1.2.3"))
        self.assertFalse(match("1.2.2", "^1.2.3"))

    def test_zero_major_keeps_minor(self):
        self.assertTrue(match("0.2.9", "^0.2.3"))
        self.assertFalse(match("0.3.0", "^0.2.3"))
        self.assertFalse(match("0.2.2", "^0.2.3"))

    def test_zero_major_zero_minor_keeps_patch(self):
        self.assertTrue(match("0.0.3", "^0.0.3"))
        self.assertFalse(match("0.0.4", "^0.0.3"))

    def test_partial_caret(self):
        self.assertTrue(match("1.9.9", "^1.2"))
        self.assertFalse(match("2.0.0", "^1.2"))
        self.assertTrue(match("0.2.9", "^0.2"))
        self.assertFalse(match("0.3.0", "^0.2"))
        self.assertTrue(match("0.0.9", "^0.0"))
        self.assertFalse(match("0.1.0", "^0.0"))
        self.assertTrue(match("0.9.9", "^0"))
        self.assertFalse(match("1.0.0", "^0"))


class TestTilde(unittest.TestCase):
    def test_basic(self):
        self.assertTrue(match("1.2.9", "~1.2.3"))
        self.assertFalse(match("1.3.0", "~1.2.3"))
        self.assertFalse(match("1.2.2", "~1.2.3"))

    def test_partial(self):
        self.assertTrue(match("1.2.9", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))
        self.assertTrue(match("1.9.9", "~1"))
        self.assertFalse(match("2.0.0", "~1"))

    def test_zero_major(self):
        self.assertTrue(match("0.2.9", "~0.2.3"))
        self.assertFalse(match("0.3.0", "~0.2.3"))


class TestPrerelease(unittest.TestCase):
    def test_prerelease_excluded_by_default(self):
        self.assertFalse(match("1.2.3-alpha", "^1.0.0"))
        self.assertFalse(match("2.0.0-rc.1", ">=1.0.0"))
        self.assertFalse(match("1.0.0-alpha", "*"))

    def test_release_still_matches(self):
        self.assertTrue(match("1.2.3", "^1.0.0"))

    def test_prerelease_allowed_same_tuple(self):
        spec = ">=1.2.3-alpha <2.0.0"
        self.assertTrue(match("1.2.3-beta", spec))
        self.assertTrue(match("1.2.3-alpha.1", spec))
        self.assertTrue(match("1.5.0", spec))

    def test_prerelease_other_tuple_still_excluded(self):
        spec = ">=1.2.3-alpha <2.0.0"
        self.assertFalse(match("1.2.4-beta", spec))
        self.assertFalse(match("1.9.9-rc.1", spec))

    def test_caret_with_prerelease_base(self):
        self.assertTrue(match("1.2.3-beta.1", "^1.2.3-alpha"))
        self.assertFalse(match("1.3.0-beta", "^1.2.3-alpha"))

    def test_prerelease_rule_is_per_or_branch(self):
        spec = "^1.0.0 || >=2.0.0-rc.1 <2.0.0"
        self.assertTrue(match("2.0.0-rc.2", spec))
        self.assertFalse(match("1.5.0-beta", spec))


class TestBest(unittest.TestCase):
    def test_picks_highest_match(self):
        versions = ["1.4.2", "1.10.0", "1.9.9", "2.0.0", "0.9.5"]
        self.assertEqual(str(best(versions, "^1.0.0")), "1.10.0")

    def test_none_when_no_match(self):
        self.assertIsNone(best(["1.0.0", "2.0.0"], "^3.0.0"))
        self.assertIsNone(best([], "*"))

    def test_skips_prerelease(self):
        versions = ["1.4.2-beta.3", "1.4.1"]
        self.assertEqual(str(best(versions, "^1.4.0")), "1.4.1")

    def test_prerelease_can_win_when_allowed(self):
        versions = ["2.0.0-rc.1", "2.0.0-rc.2", "1.9.9"]
        self.assertEqual(str(best(versions, ">=2.0.0-rc.1 <2.0.0")), "2.0.0-rc.2")

    def test_accepts_version_objects_and_range_object(self):
        versions = [parse_version("1.0.0"), parse_version("1.2.0")]
        r = parse_range("~1.0.0")
        self.assertEqual(str(best(versions, r)), "1.0.0")
        self.assertTrue(match(parse_version("1.0.0"), r))


if __name__ == "__main__":
    unittest.main()
