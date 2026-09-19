"""diffkit 防回归测试：覆盖发布群/值班记录里上报的四个缺陷。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffkit import apply_patch, parse_patch, unapply_patch, unified_diff


class TestRepeatedLinesOffset(unittest.TestCase):
    """现象 1：全重复行文件打补丁，落点偏一行。"""

    def test_change_lands_on_correct_line(self):
        old_text = "head\n" + "rate 100\n" * 10 + "tail\n"
        lines = ["head"] + ["rate 100"] * 10 + ["tail"]
        lines[5] = "rate 50"
        new_text = "\n".join(lines) + "\n"
        patch = unified_diff(old_text, new_text)
        self.assertEqual(apply_patch(old_text, patch), new_text)

    def test_hunk_header_is_one_based(self):
        old_text = "a\nb\nc\n"
        new_text = "a\nB\nc\n"
        patch = unified_diff(old_text, new_text, context=0)
        self.assertIn("@@ -2 +2 @@", patch)
        self.assertEqual(apply_patch(old_text, patch), new_text)


class TestTrailingNewline(unittest.TestCase):
    """现象 2：打完补丁文件尾换行丢失。"""

    def test_trailing_newline_preserved(self):
        old_text = "alpha\nbeta\n"
        new_text = "alpha\nbeta\ngamma\n"
        patch = unified_diff(old_text, new_text)
        self.assertEqual(apply_patch(old_text, patch), new_text)

    def test_no_newline_marker_roundtrip(self):
        old_text = "alpha\nbeta"
        new_text = "alpha\ngamma\nbeta"
        patch = unified_diff(old_text, new_text)
        self.assertIn("\\ No newline at end of file", patch)
        self.assertEqual(apply_patch(old_text, patch), new_text)

    def test_newline_added_at_eof(self):
        old_text = "alpha\nbeta"
        new_text = "alpha\nbeta\n"
        patch = unified_diff(old_text, new_text)
        self.assertEqual(apply_patch(old_text, patch), new_text)

    def test_newline_removed_at_eof(self):
        old_text = "alpha\nbeta\n"
        new_text = "alpha\nbeta"
        patch = unified_diff(old_text, new_text)
        self.assertEqual(apply_patch(old_text, patch), new_text)


class TestBaselineDrift(unittest.TestCase):
    """现象 3：补丁基线与目标不一致时静默丢改动。"""

    def test_apply_raises_on_context_mismatch(self):
        base = "\n".join(f"entry-{i} = ok" for i in range(1, 13)) + "\n"
        patched = base.replace("entry-2 = ok", "entry-2 = changed")
        patched = patched.replace("entry-11 = ok", "entry-11 = changed")
        patch = unified_diff(base, patched)
        drifted = base.replace("entry-11 = ok", "entry-11 = edited")
        with self.assertRaises(ValueError):
            apply_patch(drifted, patch)

    def test_apply_does_not_silently_drop_hunks(self):
        old_text = "x\ny\nz\n"
        patch = unified_diff(old_text, "x\nY\nz\n")
        with self.assertRaises(ValueError):
            apply_patch("x\nother\nz\n", patch)


class TestUnapply(unittest.TestCase):
    """现象 4：反向应用（回滚）报上下文不匹配。"""

    def test_unapply_appended_line(self):
        old_text = "alpha\nbeta\n"
        new_text = "alpha\nbeta\ngamma\n"
        patch = unified_diff(old_text, new_text)
        self.assertEqual(unapply_patch(new_text, patch), old_text)

    def test_apply_then_unapply_roundtrip(self):
        old_text = "head\n" + "rate 100\n" * 10 + "tail\n"
        lines = ["head"] + ["rate 100"] * 10 + ["tail"]
        lines[5] = "rate 50"
        new_text = "\n".join(lines) + "\n"
        patch = unified_diff(old_text, new_text)
        applied = apply_patch(old_text, patch)
        self.assertEqual(applied, new_text)
        self.assertEqual(unapply_patch(applied, patch), old_text)

    def test_unapply_restores_missing_trailing_newline(self):
        old_text = "alpha\nbeta"
        new_text = "alpha\nbeta\n"
        patch = unified_diff(old_text, new_text)
        self.assertEqual(unapply_patch(new_text, patch), old_text)

    def test_unapply_mismatch_raises(self):
        patch = unified_diff("a\nb\n", "a\nB\n")
        with self.assertRaises(ValueError):
            unapply_patch("a\nother\n", patch)


class TestRoundTrip(unittest.TestCase):
    """生成-应用-回滚的一般性往返。"""

    CASES = [
        ("", "new\n"),
        ("old\n", ""),
        ("", ""),
        ("a\nb\nc\n", "a\nB\nc\n"),
        ("a\nb\nc\n", "x\ny\nz\n"),
        ("same\n" * 20, "same\n" * 10 + "diff\n" + "same\n" * 9),
        ("no newline at end", "no newline at end\n"),
        ("tail\n", "tail"),
        ("one\ntwo\nthree\nfour\nfive\n",
         "one\nTWO\nthree\nfour\nFIVE\n"),
    ]

    def test_roundtrip(self):
        for old_text, new_text in self.CASES:
            with self.subTest(old=old_text, new=new_text):
                patch = unified_diff(old_text, new_text)
                self.assertEqual(apply_patch(old_text, patch), new_text)
                self.assertEqual(unapply_patch(new_text, patch), old_text)

    def test_no_diff_returns_empty_patch(self):
        self.assertEqual(unified_diff("a\nb\n", "a\nb\n"), "")

    def test_parse_patch_counts(self):
        patch = unified_diff("a\nb\nc\n", "a\nB\nc\n", context=0)
        (hunk,) = parse_patch(patch)
        self.assertEqual((hunk.old_start, hunk.old_count), (2, 1))
        self.assertEqual((hunk.new_start, hunk.new_count), (2, 1))


if __name__ == "__main__":
    unittest.main()
