"""parse_range / match / best 的区间行为测试。"""
import unittest

from verkit.range import Range, best, match, parse_range
from verkit.version import parse_version


class TestCaret(unittest.TestCase):
    def test_caret_basic(self):
        self.assertTrue(match("1.2.3", "^1.2.3"))
        self.assertTrue(match("1.9.0", "^1.2.3"))
        self.assertFalse(match("2.0.0", "^1.2.3"))
        self.assertFalse(match("1.2.2", "^1.2.3"))

    def test_caret_zero_major(self):
        self.assertTrue(match("0.2.3", "^0.2.3"))
        self.assertTrue(match("0.2.9", "^0.2.3"))
        self.assertFalse(match("0.3.0", "^0.2.3"))
        self.assertFalse(match("1.0.0", "^0.2.3"))

    def test_caret_zero_zero(self):
        self.assertTrue(match("0.0.3", "^0.0.3"))
        self.assertFalse(match("0.0.4", "^0.0.3"))

    def test_caret_missing_segments(self):
        self.assertTrue(match("1.9.9", "^1"))
        self.assertFalse(match("2.0.0", "^1"))
        self.assertTrue(match("1.2.0", "^1.2"))
        self.assertFalse(match("1.1.9", "^1.2"))
        self.assertTrue(match("0.0.9", "^0.0"))
        self.assertFalse(match("0.1.0", "^0.0"))
        self.assertTrue(match("0.9.9", "^0"))
        self.assertFalse(match("1.0.0", "^0"))

    def test_caret_with_prerelease_bound(self):
        self.assertTrue(match("1.2.3-rc.1", "^1.2.3-beta"))
        self.assertTrue(match("1.9.0", "^1.2.3-beta"))
        self.assertFalse(match("1.2.3-alpha", "^1.2.3-beta"))
        self.assertFalse(match("2.0.0", "^1.2.3-beta"))


class TestTilde(unittest.TestCase):
    def test_tilde_full(self):
        self.assertTrue(match("1.2.3", "~1.2.3"))
        self.assertTrue(match("1.2.9", "~1.2.3"))
        self.assertFalse(match("1.3.0", "~1.2.3"))
        self.assertFalse(match("1.2.2", "~1.2.3"))

    def test_tilde_zero_major(self):
        self.assertTrue(match("0.2.9", "~0.2.3"))
        self.assertFalse(match("0.3.0", "~0.2.3"))

    def test_tilde_missing_segments(self):
        self.assertTrue(match("1.2.0", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))
        self.assertTrue(match("1.9.9", "~1"))
        self.assertFalse(match("2.0.0", "~1"))
        self.assertTrue(match("0.2.5", "~0.2"))
        self.assertFalse(match("0.3.0", "~0.2"))


class TestPlainComparators(unittest.TestCase):
    def test_default_fill_zero(self):
        self.assertTrue(match("1.2.0", "1.2"))
        self.assertFalse(match("1.2.1", "1.2"))
        self.assertTrue(match("1.0.0", "=1"))
        self.assertTrue(match("1.2.0", ">=1.2"))
        self.assertFalse(match("1.1.9", ">=1.2"))

    def test_exact_and_inequality(self):
        self.assertTrue(match("1.2.3", "1.2.3"))
        self.assertTrue(match("1.2.3", "=1.2.3"))
        self.assertFalse(match("1.2.4", "1.2.3"))
        self.assertTrue(match("1.2.4", ">1.2.3"))
        self.assertFalse(match("1.2.3", ">1.2.3"))
        self.assertTrue(match("1.2.3", "<=1.2.3"))
        self.assertFalse(match("1.2.4", "<=1.2.3"))

    def test_not_equal_exact(self):
        self.assertFalse(match("1.2.3", "!=1.2.3"))
        self.assertTrue(match("1.2.4", "!=1.2.3"))
        self.assertTrue(match("0.0.1", "!=1.2.3"))

    def test_and_combination(self):
        self.assertTrue(match("1.5.0", ">=1.2.0 <2.0.0"))
        self.assertFalse(match("2.0.0", ">=1.2.0 <2.0.0"))
        self.assertFalse(match("1.1.9", ">=1.2.0 <2.0.0"))

    def test_or_combination(self):
        spec = "<1.0.0 || >=2.0.0"
        self.assertTrue(match("0.9.9", spec))
        self.assertTrue(match("2.0.0", spec))
        self.assertFalse(match("1.5.0", spec))

    def test_build_metadata_ignored(self):
        self.assertTrue(match("1.2.3+build.9", "=1.2.3"))
        self.assertTrue(match("1.2.3", "=1.2.3+build.9"))


class TestWildcard(unittest.TestCase):
    def test_minor_wildcard(self):
        self.assertTrue(match("1.0.0", "1.x"))
        self.assertTrue(match("1.9.9", "1.*"))
        self.assertFalse(match("2.0.0", "1.x"))
        self.assertFalse(match("0.9.9", "1.x"))

    def test_patch_wildcard(self):
        self.assertTrue(match("1.2.0", "1.2.x"))
        self.assertTrue(match("1.2.9", "1.2.X"))
        self.assertFalse(match("1.3.0", "1.2.x"))

    def test_star_matches_any_release(self):
        self.assertTrue(match("0.0.0", "*"))
        self.assertTrue(match("9.9.9", "x"))
        self.assertTrue(match("1.2.3", ""))

    def test_wildcard_with_inequality(self):
        self.assertTrue(match("1.2.9", "<=1.2.x"))
        self.assertFalse(match("1.3.0", "<=1.2.x"))
        self.assertTrue(match("1.3.0", ">1.2.x"))
        self.assertFalse(match("1.2.9", ">1.2.x"))
        self.assertTrue(match("1.2.0", ">=1.2.x"))
        self.assertFalse(match("1.1.9", "<1.x"))


class TestPrereleaseGate(unittest.TestCase):
    def test_prerelease_excluded_by_default(self):
        self.assertFalse(match("1.2.3-beta", "^1.2.0"))
        self.assertFalse(match("1.2.3-beta", "*"))
        self.assertFalse(match("2.0.0-rc.1", ">=1.0.0"))

    def test_prerelease_allowed_same_tuple(self):
        spec = ">=1.2.3-alpha <2.0.0"
        self.assertTrue(match("1.2.3-beta", spec))
        self.assertTrue(match("1.2.3", spec))

    def test_prerelease_not_allowed_other_tuple(self):
        spec = ">=1.2.3-alpha <2.0.0"
        self.assertFalse(match("1.2.4-beta", spec))
        self.assertFalse(match("1.9.9-rc.1", spec))

    def test_prerelease_gate_is_per_or_branch(self):
        spec = "^1.2.3 || >=2.0.0-rc.1 <3.0.0"
        self.assertTrue(match("2.0.0-rc.2", spec))
        self.assertTrue(match("1.5.0", spec))
        self.assertFalse(match("1.5.0-beta", spec))
        self.assertFalse(match("2.0.0-rc.1", "^1.2.3 || >=2.0.0 <3.0.0"))

    def test_prerelease_still_needs_comparators(self):
        self.assertFalse(match("1.2.3-alpha", ">=1.2.3-beta <2.0.0"))
        self.assertFalse(match("1.2.3-rc.1", ">1.2.3-rc.2"))


class TestParseRange(unittest.TestCase):
    def test_returns_range_object(self):
        rng = parse_range("^1.2.3")
        self.assertIsInstance(rng, Range)
        self.assertTrue(rng.match("1.5.0"))

    def test_parse_range_idempotent(self):
        rng = parse_range(">=1.0.0")
        self.assertIs(parse_range(rng), rng)

    def test_invalid_tokens_raise(self):
        for text in ("foo", ">=1.2.3.4", "1.2.3-", ">=", "v1.2.3", "!=1.x", "1.2.x-beta"):
            with self.assertRaises(ValueError, msg=text):
                parse_range(text)

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            parse_range(123)


class TestBest(unittest.TestCase):
    CANDIDATES = ["1.4.2", "1.4.2-beta.3", "1.10.0", "1.9.9", "2.0.0-rc.1", "0.9.5"]

    def test_best_picks_highest_match(self):
        self.assertEqual(str(best(self.CANDIDATES, "^1.2.0")), "1.10.0")
        self.assertEqual(str(best(self.CANDIDATES, "<1.0.0")), "0.9.5")

    def test_best_skips_prerelease_by_default(self):
        self.assertEqual(str(best(self.CANDIDATES, ">=2.0.0-rc.1")), "2.0.0-rc.1")
        self.assertIsNone(best(self.CANDIDATES, ">=2.0.0"))

    def test_best_none_when_empty(self):
        self.assertIsNone(best(self.CANDIDATES, "^3.0.0"))
        self.assertIsNone(best([], "*"))

    def test_best_accepts_version_objects(self):
        items = [parse_version(s) for s in ("1.0.0", "1.2.0", "2.0.0")]
        winner = best(items, "~1.0.0 || ~1.2.0")
        self.assertEqual(str(winner), "1.2.0")
        self.assertIsInstance(winner, type(items[0]))

    def test_best_with_or_and_not_equal(self):
        items = ["1.2.3", "1.2.4", "2.0.0"]
        self.assertEqual(str(best(items, "^1.2.0 !=1.2.4 || >=2.0.0")), "2.0.0")
        self.assertEqual(str(best(items, "^1.2.0 !=1.2.4")), "1.2.3")


if __name__ == "__main__":
    unittest.main()
