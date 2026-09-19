"""parse_range / match / best 的行为测试。"""

import unittest

from verkit import Range, Version, best, compare, match, parse_range, parse_version


class TestExactAndCompare(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(match("1.2.3", "1.2.3"))
        self.assertFalse(match("1.2.4", "1.2.3"))

    def test_partial_padded_with_zero(self):
        # 缺省段补 .0，按精确版本处理（与 npm 的 x-range 不同）
        self.assertTrue(match("1.2.0", "1.2"))
        self.assertTrue(match("1.0.0", "1"))
        self.assertFalse(match("1.2.4", "1.2"))
        self.assertFalse(match("1.5.0", "1"))

    def test_equal_prefix_and_star(self):
        self.assertTrue(match("1.2.3", "=1.2.3"))
        self.assertTrue(match("0.0.0", "*"))
        self.assertTrue(match("9.9.9", ""))

    def test_comparators(self):
        self.assertTrue(match("1.5.0", ">=1.2.0"))
        self.assertTrue(match("1.2.0", ">=1.2.0"))
        self.assertFalse(match("1.1.9", ">=1.2.0"))
        self.assertTrue(match("1.2.0", "<1.2.1"))
        self.assertTrue(match("2.0.0", ">1.9.9"))
        self.assertFalse(match("1.9.9", ">1.9.9"))
        self.assertTrue(match("1.2.5", "<=1.2.5"))

    def test_not_equal_exact(self):
        self.assertFalse(match("1.2.3", "!=1.2.3"))
        self.assertTrue(match("1.2.4", "!=1.2.3"))
        self.assertTrue(match("1.2.3", "!=1.2.4"))
        # 缺省段补 .0：!=1.2 精确排除 1.2.0
        self.assertFalse(match("1.2.0", "!=1.2"))
        self.assertTrue(match("1.2.1", "!=1.2"))

    def test_and_or(self):
        self.assertTrue(match("1.5.0", ">=1.0.0 <2.0.0"))
        self.assertFalse(match("2.0.0", ">=1.0.0 <2.0.0"))
        self.assertTrue(match("3.0.0", ">=1.0.0 <2.0.0 || >=3.0.0"))
        self.assertFalse(match("2.5.0", ">=1.0.0 <2.0.0 || >=3.0.0"))

    def test_build_metadata_ignored(self):
        self.assertTrue(match("1.2.3", "1.2.3+other"))
        self.assertTrue(match("1.2.3+a", "=1.2.3+b"))


class TestCaret(unittest.TestCase):
    def test_caret_one_and_above(self):
        self.assertTrue(match("1.2.9", "^1.2.3"))
        self.assertTrue(match("1.9.0", "^1.2.3"))
        self.assertFalse(match("1.1.0", "^1.2.3"))
        self.assertFalse(match("2.0.0", "^1.2.3"))

    def test_caret_zero_minor(self):
        # ^0.x：minor 也锁死
        self.assertTrue(match("0.2.5", "^0.2.3"))
        self.assertFalse(match("0.3.0", "^0.2.3"))
        self.assertFalse(match("0.2.2", "^0.2.3"))

    def test_caret_zero_zero_patch(self):
        # ^0.0.x：patch 也锁死（0.0.0 只匹配 0.0.0 本身）
        self.assertTrue(match("0.0.3", "^0.0.3"))
        self.assertFalse(match("0.0.4", "^0.0.3"))
        self.assertTrue(match("0.0.0", "^0.0.0"))
        self.assertFalse(match("0.0.3", "^0.0.0"))
        self.assertFalse(match("0.1.0", "^0.0.0"))

    def test_caret_partial_inputs_padded(self):
        # 缺省段先补 .0 再按 npm caret 展开：^1.2 == ^1.2.0
        self.assertTrue(match("1.0.0", "^1"))
        self.assertTrue(match("1.9.9", "^1"))
        self.assertFalse(match("2.0.0", "^1"))
        self.assertTrue(match("1.2.0", "^1.2"))
        self.assertTrue(match("1.2.9", "^1.2"))
        self.assertTrue(match("1.3.0", "^1.2"))
        self.assertFalse(match("1.1.9", "^1.2"))
        # 0.x 特例在补齐后同样生效：^0.0 == ^0.0.0，只匹配 0.0.0
        self.assertTrue(match("0.0.0", "^0.0"))
        self.assertFalse(match("0.0.9", "^0.0"))
        self.assertFalse(match("0.1.0", "^0.0"))


class TestTilde(unittest.TestCase):
    def test_tilde_full(self):
        self.assertTrue(match("1.2.9", "~1.2.3"))
        self.assertFalse(match("1.3.0", "~1.2.3"))
        self.assertFalse(match("1.2.2", "~1.2.3"))

    def test_tilde_zero(self):
        # 0.x 也只在 minor 内放开 patch
        self.assertTrue(match("0.2.9", "~0.2.3"))
        self.assertFalse(match("0.3.0", "~0.2.3"))

    def test_tilde_partial_inputs_padded(self):
        # 缺省段先补 .0 再按 npm tilde 展开：~1.2 == ~1.2.0，~1 == ~1.0.0
        self.assertTrue(match("1.2.0", "~1.2"))
        self.assertTrue(match("1.2.9", "~1.2"))
        self.assertFalse(match("1.3.0", "~1.2"))
        self.assertTrue(match("1.0.9", "~1"))
        self.assertFalse(match("1.1.0", "~1"))
        self.assertFalse(match("2.0.0", "~1"))


class TestWildcard(unittest.TestCase):
    def test_wildcard_ranges(self):
        for v in ("1.0.0", "1.5.9", "1.99.0"):
            self.assertTrue(match(v, "1.x"))
        self.assertFalse(match("2.0.0", "1.x"))
        self.assertTrue(match("1.2.0", "1.2.x"))
        self.assertTrue(match("1.2.9", "1.2.x"))
        self.assertFalse(match("1.3.0", "1.2.x"))
        self.assertTrue(match("0.0.1", "*"))

    def test_wildcard_with_comparators(self):
        # >=1.x 下界即 1.0.0（含）；>1.x 才从 2.0.0 起
        self.assertTrue(match("2.0.0", ">=1.x"))
        self.assertTrue(match("1.9.9", ">=1.x"))
        self.assertTrue(match("1.0.0", ">=1.x"))
        self.assertFalse(match("0.9.9", ">=1.x"))
        self.assertTrue(match("2.0.0", ">1.x"))
        self.assertFalse(match("1.9.9", ">1.x"))
        self.assertTrue(match("1.5.3", "<1.6.x"))
        self.assertFalse(match("1.6.0", "<1.6.x"))
        self.assertTrue(match("1.5.9", "<=1.5.x"))
        self.assertFalse(match("1.6.0", "<=1.5.x"))


class TestPrereleaseGate(unittest.TestCase):
    def test_prerelease_excluded_by_default(self):
        self.assertFalse(match("1.0.0-alpha", "*"))
        self.assertFalse(match("1.5.0-beta", "1.x"))
        self.assertFalse(match("1.2.3-rc.1", "^1.0.0"))
        self.assertFalse(match("2.0.0-rc.1", ">=1.0.0 <3.0.0"))

    def test_prerelease_allowed_for_same_triple(self):
        self.assertTrue(match("1.2.3-alpha", "^1.2.3-alpha"))
        self.assertTrue(match("1.2.3-alpha.2", ">=1.2.3-alpha"))
        self.assertTrue(match("1.0.0-rc.1", ">=1.0.0-rc.1 <2.0.0"))
        self.assertFalse(match("1.0.0-rc.2", ">=1.0.0-rc.1 <1.0.0-rc.2"))

    def test_prerelease_gate_is_per_triple(self):
        # 放行了 1.2.3 这个三元组，不代表 1.5.0 的 prerelease 也放行
        self.assertFalse(match("1.5.0-beta", "^1.2.3-alpha"))
        self.assertTrue(match("1.2.3-beta", "^1.2.3-alpha"))

    def test_prerelease_gate_scoped_per_or_branch(self):
        self.assertTrue(match("1.5.0-beta", "1.x || 1.5.0-beta"))
        self.assertTrue(match("2.0.0-beta", "^1.0.0 || 2.0.0-beta"))
        # 仅出现在 != 里的 prerelease 同样只放行同一三元组
        self.assertFalse(match("1.0.0-alpha", "!=1.0.0"))
        self.assertFalse(match("1.0.0-alpha", "* !=1.0.0-alpha"))
        self.assertTrue(match("1.0.0-beta", "* !=1.0.0-alpha"))
        self.assertFalse(match("1.0.0-alpha", "!=1.0.0-alpha"))

    def test_release_still_matches_when_prerelease_comparator_present(self):
        self.assertTrue(match("1.2.3", ">=1.2.3-alpha"))
        self.assertTrue(match("1.5.0", "^1.2.3-alpha"))

    def test_prerelease_comparator_order(self):
        self.assertTrue(match("1.2.3-beta", ">1.2.3-alpha"))
        self.assertFalse(match("1.2.2-beta", ">1.2.3-alpha"))


class TestBest(unittest.TestCase):
    CANDIDATES = [
        "1.4.2",
        "1.4.2-beta.3",
        "1.10.0",
        "1.9.9",
        "2.0.0-rc.1",
        "2.0.0-rc.1+build.7",
        "0.9.5",
    ]

    def test_best_picks_highest_satisfied(self):
        self.assertEqual(
            str(best(self.CANDIDATES, "^1.0.0")),
            "1.10.0",
        )

    def test_best_returns_none(self):
        self.assertIsNone(best(self.CANDIDATES, ">=3.0.0"))

    def test_best_with_prerelease_branch(self):
        result = best(self.CANDIDATES, "^1.4.0 || >=2.0.0-rc.1")
        # build 不参与优先级，2.0.0-rc.1 与 +build.7 优先级相同
        self.assertEqual(compare(result, "2.0.0-rc.1"), 0)
        # ^1.4.0 分支本身就放行了 1.4.x~1.x 的正式版
        self.assertEqual(str(best(self.CANDIDATES, "^1.4.0 || >=2.0.0")), "1.10.0")
        # ^1.4.2-beta.3 上界仍是 <2.0.0，正式版 1.10.0 最高
        self.assertEqual(
            str(best(self.CANDIDATES, "^1.4.2-beta.3")),
            "1.10.0",
        )
        # 只放行 1.4.2 这个三元组的 prerelease，beta.3 本身也满足
        self.assertEqual(
            str(best(["1.4.2-alpha", "1.4.2-beta.2", "1.4.2-beta.3"],
                     ">=1.4.2-beta.2 <1.4.2")),
            "1.4.2-beta.3",
        )
        self.assertIsNone(best(["1.5.0-beta"], "^1.4.2-beta.3"))

    def test_best_accepts_version_objects(self):
        versions = [parse_version(s) for s in self.CANDIDATES]
        self.assertEqual(str(best(versions, "~1.4.0")), "1.4.2")


class TestParseAndTypes(unittest.TestCase):
    def test_parse_range_object_reuse(self):
        parsed = parse_range("^1.0.0 || >=2.0.0")
        self.assertIsInstance(parsed, Range)
        self.assertEqual(str(parsed), "^1.0.0 || >=2.0.0")
        self.assertIs(parse_range(parsed), parsed)
        self.assertTrue(match(parse_version("1.5.0"), parsed))
        self.assertTrue(match("2.1.0", parsed))

    def test_match_accepts_version_object(self):
        self.assertTrue(match(Version(1, 2, 3), "^1.0.0"))

    def test_invalid_ranges_raise(self):
        for bad in (
            "abc",
            "^1.x",
            "~1.2.x.3",
            "1.x.3",
            "01.2.3",
            ">=1.x-rc.1",
            "!=1.x",
            "!=1.2.x",
            ">*",
            "1.2.3-alpha..1",
            ">= ",
        ):
            with self.assertRaises(ValueError, msg=bad):
                parse_range(bad)

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            match("1.2", "^1.0.0")
        with self.assertRaises(ValueError):
            best(["1.2"], "*")

    def test_non_string_range_raises(self):
        with self.assertRaises(ValueError):
            parse_range(123)


if __name__ == "__main__":
    unittest.main()
