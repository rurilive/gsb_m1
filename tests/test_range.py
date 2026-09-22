"""区间解析 / 匹配 / 选优 / 重叠 / 化简的行为测试。"""

import unittest

from verkit.range import best, match, normalize, overlaps, parse_range
from verkit.version import parse_version


class TestCaret(unittest.TestCase):
    def test_caret_basic(self):
        self.assertTrue(match("1.2.3", "^1.2.3"))
        self.assertTrue(match("1.9.9", "^1.2.3"))
        self.assertFalse(match("2.0.0", "^1.2.3"))
        self.assertFalse(match("1.2.2", "^1.2.3"))

    def test_caret_zero_major(self):
        # ^0.2.3 只允许 patch 级变动
        self.assertTrue(match("0.2.9", "^0.2.3"))
        self.assertFalse(match("0.3.0", "^0.2.3"))
        self.assertFalse(match("0.2.2", "^0.2.3"))

    def test_caret_zero_zero(self):
        # ^0.0.3 锁死精确版本
        self.assertTrue(match("0.0.3", "^0.0.3"))
        self.assertFalse(match("0.0.4", "^0.0.3"))

    def test_caret_zero_zero_zero(self):
        self.assertTrue(match("0.0.0", "^0.0.0"))
        self.assertFalse(match("0.0.1", "^0.0.0"))

    def test_caret_partial(self):
        self.assertTrue(match("0.9.9", "^0.x"))
        self.assertFalse(match("1.0.0", "^0.x"))
        self.assertTrue(match("0.2.5", "^0.2"))
        self.assertFalse(match("0.3.0", "^0.2"))
        self.assertTrue(match("0.0.9", "^0.0.x"))
        self.assertFalse(match("0.1.0", "^0.0.x"))
        self.assertTrue(match("1.9.9", "^1.2"))
        self.assertFalse(match("2.0.0", "^1.2"))

    def test_caret_prerelease_base(self):
        self.assertTrue(match("1.2.3", "^1.2.3-beta.2"))
        self.assertTrue(match("1.2.3-rc.1", "^1.2.3-beta.2"))
        self.assertFalse(match("2.0.0", "^1.2.3-beta.2"))


class TestTilde(unittest.TestCase):
    def test_tilde_full(self):
        self.assertTrue(match("1.2.9", "~1.2.3"))
        self.assertFalse(match("1.3.0", "~1.2.3"))
        self.assertFalse(match("1.2.2", "~1.2.3"))

    def test_tilde_partial(self):
        self.assertTrue(match("1.2.0", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))
        self.assertTrue(match("1.9.9", "~1"))
        self.assertFalse(match("2.0.0", "~1"))

    def test_tilde_zero(self):
        self.assertTrue(match("0.2.9", "~0.2.3"))
        self.assertFalse(match("0.3.0", "~0.2.3"))


class TestWildcardAndPartial(unittest.TestCase):
    def test_wildcard_patch(self):
        self.assertTrue(match("1.2.0", "1.2.x"))
        self.assertTrue(match("1.2.9", "1.2.*"))
        self.assertFalse(match("1.3.0", "1.2.x"))

    def test_wildcard_minor(self):
        self.assertTrue(match("1.0.0", "1.x"))
        self.assertTrue(match("1.99.99", "1.x"))
        self.assertFalse(match("2.0.0", "1.x"))

    def test_star_and_empty(self):
        for rng in ("*", "x", ""):
            self.assertTrue(match("1.2.3", rng))
            self.assertTrue(match("0.0.0", rng))
            # 空区间不放行 prerelease
            self.assertFalse(match("1.2.3-beta", rng))

    def test_partial_defaults_zero(self):
        self.assertTrue(match("1.2.0", "1.2"))
        self.assertTrue(match("1.2.9", "1.2"))
        self.assertFalse(match("1.3.0", "1.2"))
        self.assertTrue(match("1.0.0", "1"))
        self.assertFalse(match("2.0.0", "1"))

    def test_operator_partial(self):
        self.assertTrue(match("1.3.0", ">1.2"))
        self.assertFalse(match("1.2.9", ">1.2"))
        self.assertTrue(match("1.2.9", "<=1.2"))
        self.assertFalse(match("1.3.0", "<=1.2"))
        self.assertTrue(match("1.1.9", "<1.2"))
        self.assertFalse(match("1.2.0", "<1.2"))


class TestBooleanComposition(unittest.TestCase):
    def test_and(self):
        self.assertTrue(match("1.5.0", ">=1.0.0 <2.0.0"))
        self.assertFalse(match("2.0.0", ">=1.0.0 <2.0.0"))
        self.assertFalse(match("0.9.9", ">=1.0.0 <2.0.0"))

    def test_or(self):
        self.assertTrue(match("1.2.3", "1.2.3 || 2.0.0"))
        self.assertTrue(match("2.0.0", "1.2.3 || 2.0.0"))
        self.assertFalse(match("1.5.0", "1.2.3 || 2.0.0"))

    def test_ne_exact(self):
        self.assertFalse(match("1.2.3", ">=1.0.0 <2.0.0 !=1.2.3"))
        self.assertTrue(match("1.2.4", ">=1.0.0 <2.0.0 !=1.2.3"))

    def test_ne_partial(self):
        self.assertFalse(match("1.2.5", "!=1.2"))
        self.assertTrue(match("1.1.9", "!=1.2"))
        self.assertTrue(match("1.3.0", "!=1.2"))

    def test_exact_version(self):
        self.assertTrue(match("1.2.3", "1.2.3"))
        self.assertTrue(match("1.2.3", "=1.2.3"))
        self.assertFalse(match("1.2.4", "1.2.3"))


class TestPrereleaseGating(unittest.TestCase):
    def test_prerelease_excluded_by_default(self):
        self.assertFalse(match("1.5.0-beta", ">=1.0.0 <2.0.0"))
        self.assertFalse(match("2.0.0-rc.1", "^1.0.0 || >=2.0.0"))

    def test_prerelease_allowed_same_tuple(self):
        self.assertTrue(match("1.2.3-beta", ">1.2.3-alpha <2.0.0"))
        self.assertTrue(match("1.2.3-alpha.1", ">=1.2.3-alpha"))

    def test_prerelease_other_tuple_not_allowed(self):
        self.assertFalse(match("1.2.4-beta", ">1.2.3-alpha <2.0.0"))

    def test_prerelease_or_branch_isolation(self):
        rng = "1.2.3-alpha || >=2.0.0"
        self.assertTrue(match("1.2.3-alpha", rng))
        self.assertTrue(match("2.5.0", rng))
        # 另一分支的 prerelease 比较子不放行本分支的 prerelease
        self.assertFalse(match("2.5.0-beta", rng))

    def test_release_still_matches_prerelease_range(self):
        self.assertTrue(match("1.2.3", ">=1.2.3-alpha"))
        self.assertTrue(match("2.0.0", ">=1.2.3-alpha"))


class TestBest(unittest.TestCase):
    CANDIDATES = ["1.4.2", "1.4.2-beta.3", "1.10.0", "1.9.9",
                  "2.0.0-rc.1", "0.9.5"]

    def test_best_picks_highest(self):
        self.assertEqual(str(best(self.CANDIDATES, "^1.2.0")), "1.10.0")

    def test_best_skips_prerelease(self):
        self.assertEqual(str(best(self.CANDIDATES, ">=1.4.0 <1.5.0")), "1.4.2")

    def test_best_none_when_empty(self):
        self.assertIsNone(best(self.CANDIDATES, ">=3.0.0"))
        self.assertIsNone(best([], "*"))

    def test_best_accepts_version_objects(self):
        vs = [parse_version(s) for s in self.CANDIDATES]
        self.assertEqual(str(best(vs, "~1.9.0")), "1.9.9")


class TestOverlaps(unittest.TestCase):
    def test_overlapping(self):
        self.assertTrue(overlaps(">=1.0.0 <2.0.0", ">=1.5.0 <3.0.0"))
        self.assertTrue(overlaps("^1.2.0", "~1.5.0"))

    def test_disjoint(self):
        self.assertFalse(overlaps("<1.0.0", ">=1.0.0"))
        self.assertFalse(overlaps("1.2.3", "1.2.4"))

    def test_touching_endpoint(self):
        self.assertTrue(overlaps("<=1.2.3", ">=1.2.3"))
        self.assertFalse(overlaps("<1.2.3", ">=1.2.3"))

    def test_exclusion_kills_single_point(self):
        self.assertFalse(overlaps("1.2.3", ">=1.0.0 <2.0.0 !=1.2.3"))
        self.assertTrue(overlaps("1.2.3", ">=1.0.0 <2.0.0 !=1.2.4"))

    def test_or_branches(self):
        self.assertTrue(overlaps("1.x || 3.x", "3.2.0"))
        self.assertFalse(overlaps("1.x || 3.x", "2.x"))


class TestNormalize(unittest.TestCase):
    VERSIONS = [
        "0.9.9", "1.0.0", "1.2.3", "1.2.3-alpha", "1.2.3-beta.1",
        "1.4.9", "1.5.0", "1.9.9", "2.0.0", "2.0.0-rc.1", "2.5.0",
        "2.5.0-beta", "3.0.0", "3.0.1", "4.0.0",
    ]

    def assert_same_match_set(self, rng):
        simplified = normalize(rng)
        for v in self.VERSIONS:
            self.assertEqual(
                match(v, rng), match(v, simplified),
                f"{v} 在 {rng!r} 化简为 {simplified!r} 后结果不一致",
            )
        return simplified

    def test_merge_overlapping(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=1.5.0 <3.0.0"),
            ">=1.0.0 <3.0.0",
        )

    def test_merge_adjacent(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=2.0.0 <3.0.0"),
            ">=1.0.0 <3.0.0",
        )

    def test_no_merge_with_gap(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=2.0.1 <3.0.0"),
            ">=1.0.0 <2.0.0 || >=2.0.1 <3.0.0",
        )

    def test_no_merge_open_gap(self):
        # <2.0.0 与 >2.0.0 在 2.0.0 上有缺口，不能合并
        self.assertEqual(
            normalize("<2.0.0 || >2.0.0"),
            "<2.0.0 || >2.0.0",
        )

    def test_merge_to_unbounded(self):
        self.assertEqual(normalize("<2.0.0 || >=1.0.0"), "*")
        self.assertEqual(normalize("*"), "*")

    def test_exact_version(self):
        self.assertEqual(normalize("1.2.3"), "1.2.3")
        self.assertEqual(normalize("^1.2.3"), ">=1.2.3 <2.0.0")

    def test_empty_branch_dropped(self):
        self.assertEqual(normalize(">=2.0.0 <1.0.0"), "<0.0.0")
        self.assertEqual(normalize(">=2.0.0 <1.0.0 || 1.2.3"), "1.2.3")

    def test_ne_branch_kept_literal(self):
        out = normalize(">=1.0.0 <2.0.0 !=1.5.0 || >=1.5.0 <3.0.0")
        self.assertIn("!=1.5.0", out)
        self.assertIn(">=1.5.0 <3.0.0", out)

    def test_prerelease_branch_kept_literal(self):
        out = normalize(">=1.2.3-alpha <2.0.0 || >=2.0.0 <3.0.0")
        self.assertIn("1.2.3-alpha", out)

    def test_match_set_preserved(self):
        for rng in (
            "^1.2.0 || ~2.0.0 || >=3.0.0 <3.1.0",
            ">=1.0.0 <2.0.0 !=1.5.0 || >=2.0.0-rc.1 <3.0.0",
            "1.2.3 || 1.2.4 || >=2.0.0",
            "<1.0.0 || >=0.5.0 <2.0.0 || !=2.5.0",
        ):
            self.assert_same_match_set(rng)


class TestParseErrors(unittest.TestCase):
    def test_garbage(self):
        for bad in ("=>1.2.3", "1.2.3.4", "abc", ">=", "1.2.x-beta", "^"):
            with self.assertRaises(ValueError, msg=bad):
                parse_range(bad)

    def test_non_string(self):
        with self.assertRaises(ValueError):
            parse_range(123)

    def test_parse_range_idempotent(self):
        r = parse_range("^1.2.3")
        self.assertIs(parse_range(r), r)


if __name__ == "__main__":
    unittest.main()
