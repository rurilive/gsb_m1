"""parse_range / match / best 的行为测试（npm 语义 + prerelease 放行规则）。"""

import unittest

from verkit.range import Comparator, Range, best, match, parse_range
from verkit.version import parse_version


class TestCaret(unittest.TestCase):
    def test_basic(self):
        for version, expected in [
            ("1.2.3", True),
            ("1.9.9", True),
            ("1.2.2", False),
            ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^1.2.3"), expected)

    def test_zero_minor_locks_minor(self):
        # 0.x caret：锁定 minor，不允许升到 0.2
        for version, expected in [
            ("0.1.2", True),
            ("0.1.9", True),
            ("0.1.1", False),
            ("0.2.0", False),
            ("1.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^0.1.2"), expected)

    def test_zero_zero_patch_locks_patch(self):
        # 0.0.x caret：只允许同一个 patch
        for version, expected in [
            ("0.0.3", True),
            ("0.0.4", False),
            ("0.1.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^0.0.3"), expected)

    def test_caret_zero_zero_zero(self):
        self.assertTrue(match("0.0.0", "^0.0.0"))
        self.assertFalse(match("0.0.1", "^0.0.0"))

    def test_missing_segments_fill_zero(self):
        # 缺省段补 .0：^1.2 == ^1.2.0，^1 == ^1.0.0
        for version, expected in [
            ("1.2.0", True), ("1.9.0", True), ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^1.2"), expected)
        for version, expected in [
            ("1.0.0", True), ("1.9.0", True), ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^1"), expected)

    def test_caret_zero_major(self):
        for version, expected in [
            ("0.0.0", True), ("0.9.9", True), ("1.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^0"), expected)

    def test_caret_with_wildcards(self):
        for version, expected in [
            ("0.0.5", True), ("0.0.0", True), ("0.1.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "^0.0.x"), expected)


class TestTilde(unittest.TestCase):
    def test_locks_minor(self):
        for version, expected in [
            ("1.2.3", True), ("1.2.9", True), ("1.2.2", False),
            ("1.3.0", False), ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "~1.2.3"), expected)

    def test_missing_patch(self):
        for version, expected in [
            ("1.2.0", True), ("1.2.9", True), ("1.3.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "~1.2"), expected)

    def test_missing_minor_allows_minor_moves(self):
        for version, expected in [
            ("1.0.0", True), ("1.9.0", True), ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "~1"), expected)

    def test_zero_minor(self):
        for version, expected in [
            ("0.2.3", True), ("0.2.9", True), ("0.3.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "~0.2.3"), expected)


class TestWildcardAndExact(unittest.TestCase):
    def test_major_wildcard(self):
        for version, expected in [
            ("1.0.0", True), ("1.9.9", True),
            ("0.9.9", False), ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "1.x"), expected)

    def test_minor_wildcard(self):
        for version, expected in [
            ("1.2.0", True), ("1.2.9", True),
            ("1.3.0", False), ("2.2.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, "1.2.x"), expected)

    def test_star_matches_anything(self):
        self.assertTrue(match("0.0.0", "*"))
        self.assertTrue(match("9.9.9", "x"))
        self.assertTrue(match("9.9.9", "X"))

    def test_bare_and_equal_fill_zero(self):
        # 缺省段补 .0：1.2 即精确的 1.2.0，不是 1.2.*
        self.assertTrue(match("1.2.0", "1.2"))
        self.assertFalse(match("1.2.1", "1.2"))
        self.assertTrue(match("1.0.0", "=1"))
        self.assertFalse(match("1.0.1", "=1"))

    def test_comparators(self):
        for version, expected in [
            ("1.2.0", True), ("2.0.0", True), ("1.1.9", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, ">=1.2.0"), expected)
        self.assertTrue(match("1.9.9", "<2.0.0"))
        self.assertFalse(match("2.0.0", "<2.0.0"))
        self.assertTrue(match("1.5.0", ">1"))
        self.assertFalse(match("1.0.0", ">1"))

    def test_not_equal(self):
        self.assertFalse(match("1.2.3", "!=1.2.3"))
        self.assertTrue(match("1.2.4", "!=1.2.3"))
        self.assertFalse(match("1.2.3", ">=1.0.0 !=1.2.3"))
        self.assertTrue(match("1.2.2", ">=1.0.0 !=1.2.3"))


class TestAndOr(unittest.TestCase):
    def test_spaces_are_and(self):
        rng = ">=1.0.0 <2.0.0"
        for version, expected in [
            ("1.5.0", True), ("1.0.0", True),
            ("0.9.9", False), ("2.0.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, rng), expected)

    def test_pipe_pipe_is_or(self):
        rng = "^1.0.0 || >=2.0.0"
        for version, expected in [
            ("1.5.0", True), ("2.1.0", True),
            ("0.9.0", False), ("3.0.0", True),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, rng), expected)

    def test_three_branches(self):
        rng = "0.9.x || ^1.2.0 || >=2.0.0"
        for version, expected in [
            ("0.9.8", True), ("1.2.0", True), ("2.5.1", True),
            ("0.8.0", False), ("1.1.0", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, rng), expected)


class TestPrereleaseGating(unittest.TestCase):
    def test_prereleases_excluded_by_default(self):
        for version, rng in [
            ("1.5.0-alpha", "^1.0.0"),
            ("1.0.0-rc", "1.x"),
            ("1.2.0-rc", "1.2.x"),
            ("1.0.0-rc", "*"),
            ("1.9.0-alpha", ">=1.0.0 <2.0.0"),
            ("0.0.5-a", "^0.0.x"),
        ]:
            with self.subTest(version=version, range=rng):
                self.assertFalse(match(version, rng))

    def test_caret_with_prerelease_same_tuple(self):
        rng = "^1.0.0-alpha"
        for version, expected in [
            ("1.0.0-alpha", True),
            ("1.0.0-beta", True),
            ("1.0.0-rc.1", True),
            ("1.0.0", True),
            ("1.2.0-alpha", False),
            ("2.0.0-alpha", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, rng), expected)

    def test_zero_x_caret_with_prerelease(self):
        # 0.x caret + prerelease：只放行同一 0.1.0 元组的预发布
        rng = "^0.1.0-alpha"
        for version, expected in [
            ("0.1.0-alpha", True),
            ("0.1.0-beta", True),
            ("0.1.0", True),
            ("0.1.1-alpha", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, rng), expected)

    def test_zero_zero_caret_with_prerelease(self):
        rng = "^0.0.0-alpha"
        self.assertTrue(match("0.0.0-beta", rng))
        self.assertFalse(match("0.0.1-alpha", rng))

    def test_tilde_with_prerelease(self):
        rng = "~1.2.3-beta"
        for version, expected in [
            ("1.2.3-beta.2", True),
            ("1.2.3-rc", True),
            ("1.2.3-alpha", False),
            ("1.2.3", True),
            ("1.2.4-alpha", False),
        ]:
            with self.subTest(version=version):
                self.assertIs(match(version, rng), expected)

    def test_and_branch_gate_uses_tuple(self):
        # 显式 prerelease 只放行同一 x.y.z；1.2.0-alpha 仍被挡
        rng = ">=1.0.0-alpha <2.0.0"
        self.assertTrue(match("1.0.0-beta", rng))
        self.assertFalse(match("1.2.0-alpha", rng))

    def test_or_branches_gate_independently(self):
        rng = "^1.0.0-alpha || >=2.0.0"
        self.assertTrue(match("1.0.0-beta", rng))
        self.assertFalse(match("2.0.0-rc", rng))
        rng2 = "1.x || >=2.0.0-beta.1"
        self.assertTrue(match("2.0.0-rc.2", rng2))
        self.assertFalse(match("1.5.0-alpha", rng2))

    def test_exact_prerelease_comparator(self):
        self.assertTrue(match("1.0.0-alpha", "=1.0.0-alpha"))
        self.assertFalse(match("1.0.0-beta", "=1.0.0-alpha"))
        self.assertTrue(match("1.0.0-alpha", "1.0.0-alpha"))
        self.assertFalse(match("1.0.0-beta", "1.0.0-alpha"))

    def test_not_equal_prerelease_gate(self):
        # != 也是显式带 prerelease 的比较子：同元组预发布先放行再排除
        rng = "!=1.0.0-alpha"
        self.assertFalse(match("1.0.0-alpha", rng))
        self.assertTrue(match("1.0.0-beta", rng))
        self.assertFalse(match("1.0.0-rc", "^1.0.0 !=1.0.0"))

    def test_build_metadata_ignored_in_gate(self):
        self.assertTrue(match("1.0.0-alpha+other", ">=1.0.0-alpha+build.1"))


class TestParseRange(unittest.TestCase):
    def test_returns_range_with_raw_text(self):
        rng = parse_range(" ^1.2.0 || >=2.0.0 ")
        self.assertIsInstance(rng, Range)
        self.assertEqual(rng.raw, "^1.2.0 || >=2.0.0")
        self.assertEqual(len(rng.branches), 2)

    def test_expands_into_comparators(self):
        self.assertEqual(
            parse_range("^1.2.3").branches[0],
            (
                Comparator(">=", parse_version("1.2.3")),
                Comparator("<", parse_version("2.0.0")),
            ),
        )
        self.assertEqual(
            parse_range("^0.1.2").branches[0],
            (
                Comparator(">=", parse_version("0.1.2")),
                Comparator("<", parse_version("0.2.0")),
            ),
        )

    def test_star_branch_is_any(self):
        self.assertEqual(
            parse_range("*").branches, ((Comparator("*", None),),)
        )

    def test_accepts_range_and_version_objects(self):
        rng = parse_range("^1.0.0")
        self.assertTrue(match(parse_version("1.5.0"), rng))
        self.assertIs(parse_range(rng), rng)

    def test_invalid_ranges_raise(self):
        for bad in [
            "",
            "   ",
            "1.2.3 ||",
            "|| 1.2.3",
            "1.0.0 ||  || 2.0.0",
            ">=",
            "1.2.3.4",
            "01.2.3",
            "1.x-alpha",
            "1.2.x+build",
            ">1.x",
            "!=1.x",
            "v1.2.3",
            "1.2.3-01",
        ]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_range(bad)

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            parse_range(123)


class TestBest(unittest.TestCase):
    CANDIDATES = [
        "1.4.2",
        "1.4.2-beta.3",
        "1.10.0",
        "1.9.9",
        "2.0.0-rc.1",
        "2.0.0",
        "0.9.5",
    ]

    def test_highest_match_wins(self):
        self.assertEqual(str(best(self.CANDIDATES, "^1.0.0")), "1.10.0")
        self.assertEqual(str(best(self.CANDIDATES, ">=1.0.0")), "2.0.0")

    def test_prerelease_branch_can_win(self):
        picked = best(self.CANDIDATES, ">=2.0.0-rc.1")
        self.assertEqual(str(picked), "2.0.0")

    def test_pre_only_candidates(self):
        # 正式版缺席时，被显式放行的同元组 prerelease 可成为 best
        picked = best(["2.0.0-alpha", "2.0.0-rc.1"], ">=2.0.0-alpha")
        self.assertEqual(str(picked), "2.0.0-rc.1")

    def test_no_match_returns_none(self):
        self.assertIsNone(best(self.CANDIDATES, ">=3.0.0"))
        self.assertIsNone(best([], "^1.0.0"))

    def test_prerelease_excluded_without_gate(self):
        # 没有放行时，2.0.0-rc.1 不能成为 ^2 的最高版本
        self.assertIsNone(best(["2.0.0-rc.1"], "^2.0.0"))

    def test_accepts_version_objects(self):
        candidates = [parse_version(s) for s in self.CANDIDATES]
        self.assertEqual(str(best(candidates, "1.4.x")), "1.4.2")

    def test_reuses_parsed_range(self):
        rng = parse_range("~1.4.0")
        self.assertEqual(str(best(self.CANDIDATES, rng)), "1.4.2")


if __name__ == "__main__":
    unittest.main()
