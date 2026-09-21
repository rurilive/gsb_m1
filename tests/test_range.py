"""区间能力的边界测试：parse_range / match / best / overlaps / normalize。"""

import unittest

from verkit.range import best, match, normalize, overlaps, parse_range
from verkit.version import parse_version


class TestCaret(unittest.TestCase):
    def test_caret_basic(self):
        self.assertTrue(match("1.2.3", "^1.2.3"))
        self.assertTrue(match("1.9.9", "^1.2.3"))
        self.assertFalse(match("2.0.0", "^1.2.3"))
        self.assertFalse(match("1.2.2", "^1.2.3"))

    def test_caret_zero_minor_locked(self):
        # ^0.2.3 := >=0.2.3 <0.3.0
        self.assertTrue(match("0.2.9", "^0.2.3"))
        self.assertFalse(match("0.3.0", "^0.2.3"))
        self.assertFalse(match("0.2.2", "^0.2.3"))

    def test_caret_zero_zero_patch_locked(self):
        # ^0.0.3 := >=0.0.3 <0.0.4
        self.assertTrue(match("0.0.3", "^0.0.3"))
        self.assertFalse(match("0.0.4", "^0.0.3"))

    def test_caret_partial(self):
        # ^1 := <2.0.0；^0.2 := <0.3.0；^0.0 := <0.1.0；^0 := <1.0.0
        self.assertTrue(match("1.9.9", "^1"))
        self.assertFalse(match("2.0.0", "^1"))
        self.assertTrue(match("0.2.9", "^0.2"))
        self.assertFalse(match("0.3.0", "^0.2"))
        self.assertTrue(match("0.0.9", "^0.0"))
        self.assertFalse(match("0.1.0", "^0.0"))
        self.assertTrue(match("0.9.9", "^0"))
        self.assertFalse(match("1.0.0", "^0"))

    def test_caret_with_prerelease_floor(self):
        self.assertTrue(match("1.2.3-rc.1", "^1.2.3-beta"))
        self.assertTrue(match("1.5.0", "^1.2.3-beta"))
        self.assertFalse(match("2.0.0-alpha", "^1.2.3-beta"))


class TestTilde(unittest.TestCase):
    def test_tilde_full(self):
        # ~1.2.3 := >=1.2.3 <1.3.0
        self.assertTrue(match("1.2.9", "~1.2.3"))
        self.assertFalse(match("1.3.0", "~1.2.3"))
        self.assertFalse(match("1.2.2", "~1.2.3"))

    def test_tilde_partial(self):
        # ~1.2 := <1.3.0；~1 := <2.0.0；~0.2 := <0.3.0
        self.assertTrue(match("1.2.0", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))
        self.assertTrue(match("1.9.0", "~1"))
        self.assertFalse(match("2.0.0", "~1"))
        self.assertTrue(match("0.2.5", "~0.2"))
        self.assertFalse(match("0.3.0", "~0.2"))


class TestComparators(unittest.TestCase):
    def test_missing_parts_fill_zero(self):
        self.assertTrue(match("1.2.0", ">=1.2"))
        self.assertTrue(match("1.2.0", "1.2"))  # 裸版本等价于 =1.2.0
        self.assertFalse(match("1.2.1", "1.2"))
        self.assertTrue(match("1.0.0", "1"))

    def test_and_chain(self):
        rng = ">=1.2.0 <1.5.0"
        self.assertTrue(match("1.3.0", rng))
        self.assertFalse(match("1.5.0", rng))
        self.assertFalse(match("1.1.9", rng))

    def test_or_branches(self):
        rng = "^1.2.0 || >=2.0.0"
        self.assertTrue(match("1.9.0", rng))
        self.assertTrue(match("3.1.0", rng))
        self.assertFalse(match("1.1.0", rng))

    def test_not_equal(self):
        rng = ">=1.0.0 <2.0.0 !=1.5.0"
        self.assertTrue(match("1.4.9", rng))
        self.assertFalse(match("1.5.0", rng))
        self.assertTrue(match("1.5.1", rng))
        self.assertFalse(match("1.2.0", "!=1.2"))  # != 缺省同样补 .0

    def test_wildcards(self):
        self.assertTrue(match("1.9.9", "1.x"))
        self.assertFalse(match("2.0.0", "1.x"))
        self.assertTrue(match("1.2.9", "1.2.x"))
        self.assertFalse(match("1.3.0", "1.2.x"))
        self.assertTrue(match("9.9.9", "*"))
        self.assertTrue(match("1.2.0", "1.2.*"))
        self.assertFalse(match("0.0.1", "1.2.*"))

    def test_invalid_ranges(self):
        for text in ("^1.2.3.4", ">=1.x", "1.2.x.3", "abc", "1.02.3", "!=1.x"):
            with self.assertRaises(ValueError, msg=text):
                parse_range(text)


class TestPrereleaseGating(unittest.TestCase):
    def test_prerelease_excluded_by_default(self):
        self.assertFalse(match("1.0.1-alpha", ">=1.0.0"))
        self.assertFalse(match("2.0.0-rc.1", "^1.2.0 || >=2.0.0"))
        self.assertFalse(match("1.2.3-alpha", "1.2.x"))

    def test_prerelease_allowed_when_explicit(self):
        rng = ">=1.0.0-alpha <2.0.0"
        self.assertTrue(match("1.0.0-beta", rng))
        self.assertTrue(match("1.5.0", rng))

    def test_prerelease_only_same_tuple(self):
        rng = ">=1.0.0-alpha <2.0.0"
        # 只有 1.0.0 这个 x.y.z 被显式放行
        self.assertFalse(match("1.0.1-alpha", rng))
        # 比较子显式携带 2.0.0 的 prerelease 时，该 tuple 才被放行
        self.assertTrue(match("2.0.0-alpha", ">=1.0.0-alpha <2.0.0-alpha.1"))

    def test_prerelease_gating_is_per_branch(self):
        rng = ">=1.0.0-alpha <1.5.0 || >=2.0.0 <3.0.0"
        self.assertTrue(match("1.0.0-rc.1", rng))
        self.assertFalse(match("2.0.0-rc.1", rng))  # 第二分支没有放行
        self.assertTrue(match("2.1.0", rng))


class TestBest(unittest.TestCase):
    def test_best_picks_highest(self):
        versions = ["1.4.2", "1.10.0", "1.9.9", "2.0.0", "0.9.5"]
        self.assertEqual(str(best(versions, "^1.2.0")), "1.10.0")
        self.assertEqual(str(best(versions, ">=0.1.0")), "2.0.0")

    def test_best_none_when_empty(self):
        self.assertIsNone(best(["0.1.0", "0.2.0"], "^1.0.0"))
        self.assertIsNone(best([], "*"))

    def test_best_skips_gated_prerelease(self):
        versions = ["1.0.0-alpha", "0.9.9"]
        self.assertEqual(str(best(versions, ">=1.0.0-alpha <2.0.0")), "1.0.0-alpha")
        self.assertEqual(str(best(versions, ">=0.1.0")), "0.9.9")

    def test_best_accepts_version_objects(self):
        versions = [parse_version("1.0.0"), parse_version("1.2.0")]
        self.assertEqual(str(best(versions, "~1.0.0")), "1.0.0")


class TestOverlaps(unittest.TestCase):
    def test_overlap_basic(self):
        self.assertTrue(overlaps("^1.2.0", "~1.4.0"))
        self.assertFalse(overlaps("^1.2.0", "^2.0.0"))
        self.assertTrue(overlaps(">=1.0.0 <2.0.0", ">1.5.0"))

    def test_overlap_touching_bounds(self):
        self.assertTrue(overlaps("<=1.2.3", ">=1.2.3"))
        self.assertFalse(overlaps("<1.2.3", ">=1.2.3"))
        self.assertFalse(overlaps(">2.0.0", "<1.0.0"))

    def test_overlap_with_not_equal(self):
        self.assertFalse(overlaps("=1.2.3", "!=1.2.3"))
        self.assertTrue(overlaps("=1.2.3", "!=1.2.4"))
        self.assertTrue(overlaps("!=1.0.0", "!=1.0.1"))

    def test_overlap_prerelease(self):
        self.assertTrue(overlaps(">=1.0.0-alpha <1.0.0", ">1.0.0-beta <1.0.0"))
        # 交集只剩 1.0.0 的 prerelease，但第二区间未放行 -> 不重叠
        self.assertFalse(overlaps(">=1.0.0-alpha <1.0.0", ">=1.0.0 <2.0.0"))

    def test_overlap_across_or_branches(self):
        self.assertTrue(overlaps("^1.0.0 || ^3.0.0", ">=2.5.0 <3.5.0"))
        self.assertFalse(overlaps("^1.0.0 || ^3.0.0", ">=2.0.0 <3.0.0"))


class TestNormalize(unittest.TestCase):
    def test_merge_overlapping(self):
        self.assertEqual(normalize("^1.2.0 || ^1.5.0"), ">=1.2.0 <2.0.0")

    def test_merge_adjacent(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 || >=2.0.0 <3.0.0"), ">=1.0.0 <3.0.0"
        )

    def test_gap_is_kept(self):
        self.assertEqual(
            normalize(">=1.0.0 <1.5.0 || >=1.6.0 <2.0.0"),
            ">=1.0.0 <1.5.0 || >=1.6.0 <2.0.0",
        )

    def test_point_and_any(self):
        self.assertEqual(normalize("=1.2.3 || =1.2.3"), "1.2.3")
        self.assertEqual(normalize("*"), "*")
        self.assertEqual(normalize(">2.0.0 <1.0.0"), "<0.0.0")

    def test_not_equal_branch_preserved(self):
        self.assertEqual(
            normalize(">=1.0.0 <2.0.0 !=1.5.0"), ">=1.0.0 <2.0.0 !=1.5.0"
        )

    def test_normalize_preserves_match_set(self):
        versions = [
            "0.9.9", "1.0.0", "1.2.0", "1.2.3", "1.4.9", "1.5.0",
            "1.5.1", "1.9.9", "2.0.0", "2.0.1", "3.0.0",
            "1.2.3-alpha", "2.0.0-rc.1",
        ]
        for rng in (
            "^1.2.0 || ^1.4.0",
            ">=1.0.0 <2.0.0 || >=2.0.0 <3.0.0",
            "1.x || >=2.0.0 <=2.0.1",
            ">=1.0.0 <2.0.0 !=1.5.0 || ~0.9.0",
            ">=1.0.0-alpha <2.0.0 || =3.0.0",
        ):
            simplified = normalize(rng)
            before = {v for v in versions if match(v, rng)}
            after = {v for v in versions if match(v, simplified)}
            self.assertEqual(before, after, msg=f"{rng} -> {simplified}")


if __name__ == "__main__":
    unittest.main()
