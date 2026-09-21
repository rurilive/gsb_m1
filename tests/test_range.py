"""区间能力（parse_range / match / best / overlaps / normalize）的测试。"""

import unittest

from verkit.range import best, match, normalize, overlaps, parse_range
from verkit.version import parse_version


class TestParseAndMatch(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(match("1.2.3", "1.2.3"))
        self.assertFalse(match("1.2.4", "1.2.3"))

    def test_default_fill_zero(self):
        self.assertTrue(match("1.2.0", ">=1.2"))
        self.assertFalse(match("1.1.9", ">=1.2"))
        self.assertTrue(match("1.2.0", "<=1.2"))
        self.assertFalse(match("1.2.1", "<=1.2"))

    def test_wildcard_patch(self):
        self.assertTrue(match("1.2.0", "1.2.x"))
        self.assertTrue(match("1.2.9", "1.2.x"))
        self.assertFalse(match("1.3.0", "1.2.x"))

    def test_wildcard_minor(self):
        self.assertTrue(match("1.99.0", "1.x"))
        self.assertFalse(match("2.0.0", "1.x"))

    def test_star_and_empty(self):
        for rng in ("*", ""):
            self.assertTrue(match("1.2.3", rng))
            self.assertFalse(match("1.2.3-alpha", rng))

    def test_and_space(self):
        rng = ">=1.2.0 <2.0.0"
        self.assertTrue(match("1.5.0", rng))
        self.assertFalse(match("1.1.9", rng))
        self.assertFalse(match("2.0.0", rng))

    def test_or(self):
        rng = "<1.0.0 || >=2.0.0"
        self.assertTrue(match("0.9.9", rng))
        self.assertTrue(match("2.0.0", rng))
        self.assertFalse(match("1.5.0", rng))

    def test_not_equal(self):
        rng = ">=1.2.0 <1.3.0 !=1.2.3"
        self.assertTrue(match("1.2.4", rng))
        self.assertFalse(match("1.2.3", rng))
        self.assertFalse(match("1.3.0", rng))

    def test_invalid(self):
        for rng in (">=abc", "1.2.x-beta", "1.2.3.4", ">*", 123):
            with self.assertRaises(ValueError):
                parse_range(rng)

    def test_accepts_version_and_range_objects(self):
        r = parse_range("^1.2.0")
        self.assertTrue(match(parse_version("1.3.0"), r))
        self.assertFalse(match(parse_version("2.0.0"), r))


class TestCaret(unittest.TestCase):
    def test_basic(self):
        rng = "^1.2.3"
        self.assertTrue(match("1.2.3", rng))
        self.assertTrue(match("1.9.0", rng))
        self.assertFalse(match("2.0.0", rng))
        self.assertFalse(match("1.2.2", rng))

    def test_zero_major(self):
        rng = "^0.2.3"
        self.assertTrue(match("0.2.9", rng))
        self.assertFalse(match("0.3.0", rng))
        self.assertFalse(match("0.2.2", rng))

    def test_zero_zero(self):
        rng = "^0.0.3"
        self.assertTrue(match("0.0.3", rng))
        self.assertFalse(match("0.0.4", rng))

    def test_zero_wildcard(self):
        self.assertTrue(match("0.9.9", "^0.x"))
        self.assertFalse(match("1.0.0", "^0.x"))
        self.assertTrue(match("0.0.9", "^0.0.x"))
        self.assertFalse(match("0.1.0", "^0.0.x"))

    def test_wildcard(self):
        rng = "^1.2.x"
        self.assertTrue(match("1.2.0", rng))
        self.assertTrue(match("1.9.9", rng))
        self.assertFalse(match("2.0.0", rng))


class TestTilde(unittest.TestCase):
    def test_basic(self):
        rng = "~1.2.3"
        self.assertTrue(match("1.2.9", rng))
        self.assertFalse(match("1.3.0", rng))
        self.assertFalse(match("1.2.2", rng))

    def test_partial(self):
        self.assertTrue(match("1.2.0", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))
        self.assertTrue(match("1.9.9", "~1"))
        self.assertFalse(match("2.0.0", "~1"))

    def test_zero(self):
        rng = "~0.2.3"
        self.assertTrue(match("0.2.9", rng))
        self.assertFalse(match("0.3.0", rng))


class TestPrerelease(unittest.TestCase):
    def test_excluded_by_default(self):
        self.assertFalse(match("1.5.0-alpha", ">=1.0.0 <2.0.0"))
        self.assertFalse(match("2.0.0-rc.1", "^1.0.0"))

    def test_allowed_when_same_triple_gated(self):
        rng = ">=1.2.3-alpha <2.0.0"
        self.assertTrue(match("1.2.3-alpha", rng))
        self.assertTrue(match("1.2.3-beta", rng))
        self.assertTrue(match("1.5.0", rng))
        # 其他 x.y.z 的预发布仍不放行
        self.assertFalse(match("1.2.4-alpha", rng))
        self.assertFalse(match("1.2.2-alpha", rng))

    def test_gating_is_per_or_branch(self):
        rng = ">=1.2.3-alpha <1.2.3 || >=2.0.0"
        self.assertTrue(match("1.2.3-rc.1", rng))
        self.assertTrue(match("2.5.0", rng))
        self.assertFalse(match("2.5.0-alpha", rng))

    def test_exact_prerelease(self):
        self.assertTrue(match("1.0.0-rc.1", "1.0.0-rc.1"))
        self.assertFalse(match("1.0.0-rc.2", "1.0.0-rc.1"))


class TestBest(unittest.TestCase):
    def test_picks_highest(self):
        got = best(["1.2.3", "1.4.0", "2.0.0"], "^1.0.0")
        self.assertEqual(got, parse_version("1.4.0"))

    def test_none_when_empty(self):
        self.assertIsNone(best(["2.0.0", "0.9.9"], "^1.0.0"))
        self.assertIsNone(best([], "*"))

    def test_skips_ungated_prerelease(self):
        got = best(["1.5.0-alpha", "1.4.0"], "^1.0.0")
        self.assertEqual(got, parse_version("1.4.0"))

    def test_uses_gated_prerelease(self):
        got = best(["1.2.3-rc.2", "1.2.3-rc.1", "1.2.2"], ">=1.2.3-rc.1 <2.0.0")
        self.assertEqual(got, parse_version("1.2.3-rc.2"))

    def test_accepts_version_objects(self):
        got = best([parse_version("1.0.0"), parse_version("1.1.0")], "~1.0.0")
        self.assertEqual(got, parse_version("1.0.0"))


class TestOverlaps(unittest.TestCase):
    def test_overlap(self):
        self.assertTrue(overlaps(">=1.0.0 <2.0.0", ">=1.5.0 <3.0.0"))

    def test_disjoint(self):
        self.assertFalse(overlaps("<1.0.0", ">=1.0.0"))
        self.assertFalse(overlaps("^1.0.0", "^2.0.0"))

    def test_touching_inclusive(self):
        self.assertTrue(overlaps("<=1.0.0", ">=1.0.0"))
        self.assertFalse(overlaps("<1.0.0", ">1.0.0"))

    def test_exclusion(self):
        self.assertFalse(overlaps("!=1.2.3", "1.2.3"))
        self.assertTrue(overlaps("!=1.2.3", "1.2.4"))
        self.assertFalse(overlaps(">1.2.3 <1.2.4", "1.2.3"))

    def test_prerelease_gap(self):
        self.assertTrue(overlaps(">=1.2.3-alpha <1.2.3", "1.2.3-beta"))
        self.assertFalse(overlaps(">1.2.3 <1.2.4", "1.2.4-alpha"))

    def test_or_branches(self):
        self.assertTrue(overlaps("<1.0.0 || >=2.0.0", "2.5.0"))
        self.assertFalse(overlaps("<1.0.0 || >=2.0.0", "^1.2.0"))


class TestNormalize(unittest.TestCase):
    def test_merges_overlap(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=1.5.0 <3.0.0"),
            ">=1.0.0 <3.0.0",
        )

    def test_merges_adjacent(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=2.0.0 <3.0.0"),
            ">=1.0.0 <3.0.0",
        )

    def test_keeps_gap(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0"),
            ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0",
        )

    def test_point_absorbed(self):
        self.assertEqual(normalize("1.2.3 || >=1.2.3 <2.0.0"), ">=1.2.3 <2.0.0")

    def test_keeps_prerelease_and_neq_branches(self):
        self.assertEqual(normalize("!=1.2.3"), "!=1.2.3")
        self.assertEqual(
            normalize(">=1.2.3-alpha <2.0.0"), ">=1.2.3-alpha <2.0.0"
        )

    def test_unsatisfiable_branch_dropped(self):
        self.assertEqual(normalize(">2.0.0 <1.0.0 || 1.5.0"), "1.5.0")

    def test_idempotent(self):
        rng = ">=1.0.0 <2.0.0 || >=1.5.0 <3.0.0 || !=3.5.0"
        self.assertEqual(normalize(normalize(rng)), normalize(rng))

    def test_match_set_identical(self):
        ranges = [
            ">=1.0.0 <2.0.0 || >=1.5.0 <3.0.0",
            ">=1.0.0 <2.0.0 || >=2.0.0 <3.0.0",
            "1.2.3 || >=1.2.3 <2.0.0",
            "^1.2.0 || ~2.4.0",
            ">=1.2.3-alpha <2.0.0 || >=2.5.0",
            ">=1.0.0 <2.0.0 !=1.5.0 || 2.5.x",
            "1.x || 2.x",
        ]
        versions = [
            "0.9.9", "1.0.0", "1.2.3", "1.2.4", "1.5.0", "1.9.9",
            "2.0.0", "2.4.9", "2.5.0", "2.5.1", "2.9.9", "3.0.0",
            "1.2.3-alpha", "1.2.3-beta", "1.5.0-alpha", "2.0.0-rc.1",
        ]
        for rng in ranges:
            simplified = normalize(rng)
            for v in versions:
                self.assertEqual(
                    match(v, rng), match(v, simplified),
                    f"{v} 在 {rng!r} 化简为 {simplified!r} 后结果不一致",
                )


if __name__ == "__main__":
    unittest.main()
