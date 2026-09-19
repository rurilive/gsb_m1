"""diffkit 防回归测试：覆盖四个已修复缺陷及正反向往返一致性。"""

import unittest

from diffkit import apply_patch, parse_patch, unapply_patch, unified_diff


class RepeatedLinesOffsetTest(unittest.TestCase):
    """现象 1：全是重复行的文件，补丁落点整体偏移一行。"""

    def test_change_lands_on_correct_line(self):
        old = "head\n" + "rate 100\n" * 10 + "tail\n"
        lines = ["head"] + ["rate 100"] * 10 + ["tail"]
        lines[5] = "rate 50"
        new = "\n".join(lines) + "\n"
        patch = unified_diff(old, new)
        applied = apply_patch(old, patch)
        self.assertEqual(applied, new)
        self.assertEqual(applied.splitlines()[5], "rate 50")
        self.assertEqual(applied.splitlines()[4], "rate 100")
        self.assertEqual(applied.splitlines()[6], "rate 100")


class TrailingNewlineTest(unittest.TestCase):
    """现象 2：应用补丁后文件尾换行丢失。"""

    def test_apply_preserves_trailing_newline(self):
        old = "a\nb\nc\n"
        new = "a\nB\nc\n"
        patch = unified_diff(old, new)
        applied = apply_patch(old, patch)
        self.assertEqual(applied, new)
        self.assertTrue(applied.endswith("\n"))

    def test_apply_preserves_missing_trailing_newline(self):
        old = "a\nb\nc"
        new = "a\nB\nc"
        patch = unified_diff(old, new)
        self.assertIn("\\ No newline at end of file", patch)
        applied = apply_patch(old, patch)
        self.assertEqual(applied, new)
        self.assertFalse(applied.endswith("\n"))

    def test_trailing_newline_only_change_produces_patch(self):
        old = "a\nb\n"
        new = "a\nb"
        patch = unified_diff(old, new)
        self.assertNotEqual(patch, "")
        self.assertEqual(apply_patch(old, patch), new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_marker_follows_its_own_line(self):
        patch = unified_diff("x\ny", "x\nz")
        body = patch.splitlines()
        idx = body.index("-y")
        self.assertEqual(body[idx + 1], "\\ No newline at end of file")
        idx = body.index("+z")
        self.assertEqual(body[idx + 1], "\\ No newline at end of file")


class BaselineMismatchTest(unittest.TestCase):
    """现象 3：补丁基线与目标版本不一致时静默丢改动。"""

    def test_apply_raises_on_drifted_baseline(self):
        base = "\n".join(f"entry-{i} = ok" for i in range(1, 13)) + "\n"
        patched = base.replace("entry-2 = ok", "entry-2 = changed")
        patched = patched.replace("entry-11 = ok", "entry-11 = changed")
        patch = unified_diff(base, patched)
        drifted = base.replace("entry-11 = ok", "entry-11 = edited")
        with self.assertRaises(ValueError):
            apply_patch(drifted, patch)

    def test_apply_raises_on_context_mismatch(self):
        old = "one\ntwo\nthree\n"
        new = "one\ntwo\nTHREE\n"
        patch = unified_diff(old, new)
        drifted = old.replace("two", "TWO")
        with self.assertRaises(ValueError):
            apply_patch(drifted, patch)


class UnapplyTest(unittest.TestCase):
    """现象 4：反向应用（回滚）报错失败。"""

    def test_unapply_appended_line(self):
        old = "alpha\nbeta\n"
        new = "alpha\nbeta\ngamma\n"
        patch = unified_diff(old, new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_unapply_prepended_line(self):
        old = "beta\n"
        new = "alpha\nbeta\n"
        patch = unified_diff(old, new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_unapply_deleted_line(self):
        old = "alpha\nbeta\ngamma\n"
        new = "alpha\ngamma\n"
        patch = unified_diff(old, new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_unapply_mismatch_raises(self):
        old = "alpha\nbeta\n"
        new = "alpha\nBETA\n"
        patch = unified_diff(old, new)
        with self.assertRaises(ValueError):
            unapply_patch("alpha\ngamma\n", patch)


class RoundTripTest(unittest.TestCase):
    """正反向往返一致性：apply 得到 new，unapply 还原 old。"""

    CASES = [
        ("", "x\n"),
        ("x\n", ""),
        ("", ""),
        ("a\nb\nc\n", "a\nB\nc\n"),
        ("a\nb\nc", "a\nB\nc"),
        ("a\nb\nc\n", "a\nb\nc"),
        ("a\nb\nc", "a\nb\nc\n"),
        ("head\n" + "rate 100\n" * 10 + "tail\n",
         "head\n" + "rate 100\n" * 4 + "rate 50\n" + "rate 100\n" * 5 + "tail\n"),
        ("one\ntwo\nthree\n", "zero\none\ntwo\nthree\n"),
        ("one\ntwo\nthree\n", "one\ntwo\n"),
        ("same\nsame\nsame\n", "same\nsame\nsame\nsame\n"),
        ("no newline", "no newline either"),
        ("a\n\nb\n", "a\nb\n"),
    ]

    def test_roundtrip(self):
        for old, new in self.CASES:
            with self.subTest(old=old, new=new):
                patch = unified_diff(old, new)
                if old == new:
                    self.assertEqual(patch, "")
                    continue
                self.assertEqual(apply_patch(old, patch), new)
                self.assertEqual(unapply_patch(new, patch), old)

    def test_parse_patch_counts(self):
        patch = unified_diff("a\nb\nc\n", "a\nB\nc\n")
        hunks = parse_patch(patch)
        self.assertEqual(len(hunks), 1)
        hunk = hunks[0]
        self.assertEqual((hunk.old_start, hunk.old_count), (1, 3))
        self.assertEqual((hunk.new_start, hunk.new_count), (1, 3))
        self.assertEqual(len(hunk.lines), 4)


if __name__ == "__main__":
    unittest.main()
