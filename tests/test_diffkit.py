"""diffkit 回归测试：覆盖发布事故中的四个现象。"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffkit import apply_patch, parse_patch, unapply_patch, unified_diff


class RepeatedLinesTest(unittest.TestCase):
    """现象 1：重复行文件上补丁落点偏移。"""

    def test_change_lands_on_exact_line(self):
        old = "head\n" + "rate 100\n" * 10 + "tail\n"
        lines = ["head"] + ["rate 100"] * 10 + ["tail"]
        lines[5] = "rate 50"
        new = "\n".join(lines) + "\n"
        patch = unified_diff(old, new)
        applied = apply_patch(old, patch)
        self.assertEqual(applied, new)
        applied_lines = applied.splitlines()
        self.assertEqual(applied_lines[5], "rate 50")
        self.assertEqual(applied_lines[4], "rate 100")
        self.assertEqual(applied_lines[6], "rate 100")

    def test_insert_into_empty_file(self):
        patch = unified_diff("", "x\ny\n")
        self.assertIn("@@ -0,0 +1,2 @@", patch)
        self.assertEqual(apply_patch("", patch), "x\ny\n")


class TrailingNewlineTest(unittest.TestCase):
    """现象 2：应用补丁后文件尾换行丢失。"""

    def test_apply_keeps_trailing_newline(self):
        old = "a\nb\nc\n"
        new = "a\nB\nc\n"
        applied = apply_patch(old, unified_diff(old, new))
        self.assertEqual(applied, new)
        self.assertTrue(applied.endswith("\n"))

    def test_marker_emitted_for_missing_newline(self):
        patch = unified_diff("a\nb", "a\nc")
        self.assertIn("\\ No newline at end of file", patch)

    def test_newline_only_change(self):
        for old, new in [("a\nb", "a\nb\n"), ("a\nb\n", "a\nb")]:
            patch = unified_diff(old, new)
            self.assertNotEqual(patch, "")
            self.assertEqual(apply_patch(old, patch), new)
            self.assertEqual(unapply_patch(new, patch), old)

    def test_no_newline_roundtrip(self):
        cases = [
            ("a\nb", "a\nc"),
            ("a\nb", "a\nc\n"),
            ("a\nb\n", "a\nc"),
            ("x\ny\nz", "x\nY\nz"),
            ("only", "changed"),
        ]
        for old, new in cases:
            with self.subTest(old=old, new=new):
                patch = unified_diff(old, new)
                self.assertEqual(apply_patch(old, patch), new)
                self.assertEqual(unapply_patch(new, patch), old)


class BaselineMismatchTest(unittest.TestCase):
    """现象 3：补丁基线与目标不一致时必须报错，不得静默产出。"""

    def test_apply_raises_on_drift(self):
        base = "\n".join(f"entry-{i} = ok" for i in range(1, 13)) + "\n"
        patched = base.replace("entry-2 = ok", "entry-2 = changed")
        patched = patched.replace("entry-11 = ok", "entry-11 = changed")
        patch = unified_diff(base, patched)
        drifted = base.replace("entry-11 = ok", "entry-11 = edited")
        with self.assertRaises(ValueError):
            apply_patch(drifted, patch)

    def test_unapply_raises_on_mismatch(self):
        old = "alpha\nbeta\n"
        new = "alpha\nbeta\ngamma\n"
        patch = unified_diff(old, new)
        with self.assertRaises(ValueError):
            unapply_patch("alpha\nbeta\ndelta\n", patch)


class RollbackTest(unittest.TestCase):
    """现象 4：反向应用（回滚）失败。"""

    def test_unapply_pure_addition(self):
        old = "alpha\nbeta\n"
        new = "alpha\nbeta\ngamma\n"
        patch = unified_diff(old, new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_unapply_pure_deletion(self):
        old = "alpha\nbeta\ngamma\n"
        new = "alpha\nbeta\n"
        patch = unified_diff(old, new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_unapply_insert_at_head(self):
        old = "b\nc\n"
        new = "a\nb\nc\n"
        patch = unified_diff(old, new)
        self.assertEqual(apply_patch(old, patch), new)
        self.assertEqual(unapply_patch(new, patch), old)


class RoundTripTest(unittest.TestCase):
    """apply/unapply 往返一致性。"""

    CASES = [
        ("", "x\n"),
        ("x\n", ""),
        ("a\nb\nc\n", "a\nB\nc\n"),
        ("a\nb\nc\n", "a\nb\nc\nd\ne\n"),
        ("a\nb\nc\nd\ne\n", "a\ne\n"),
        ("one\ntwo\nthree\n", "three\ntwo\none\n"),
        ("same\nsame\nsame\n", "same\nDIFF\nsame\n"),
        ("head\n", "head\n"),
        ("no newline", "no newline\n"),
    ]

    def test_roundtrip_cases(self):
        for old, new in self.CASES:
            with self.subTest(old=old, new=new):
                patch = unified_diff(old, new)
                self.assertEqual(apply_patch(old, patch), new)
                self.assertEqual(unapply_patch(new, patch), old)

    def test_no_diff_returns_empty(self):
        self.assertEqual(unified_diff("a\nb\n", "a\nb\n"), "")
        self.assertEqual(unified_diff("", ""), "")

    def test_random_edits_roundtrip(self):
        rng = random.Random(20260919)
        words = ["alpha", "beta", "gamma", "delta", "rate 100", "x"]
        for _ in range(200):
            old_lines = [rng.choice(words) for _ in range(rng.randint(0, 20))]
            new_lines = list(old_lines)
            for _ in range(rng.randint(1, 5)):
                op = rng.choice(["ins", "del", "mod"])
                if op == "ins" or not new_lines:
                    new_lines.insert(rng.randint(0, len(new_lines)),
                                     rng.choice(words))
                elif op == "del":
                    new_lines.pop(rng.randrange(len(new_lines)))
                else:
                    new_lines[rng.randrange(len(new_lines))] = rng.choice(words)
            old = "\n".join(old_lines) + ("\n" if rng.random() < 0.7 else "")
            new = "\n".join(new_lines) + ("\n" if rng.random() < 0.7 else "")
            if not old_lines:
                old = ""
            if not new_lines:
                new = ""
            patch = unified_diff(old, new)
            self.assertEqual(apply_patch(old, patch), new,
                             msg=f"apply: {old!r} -> {new!r}")
            self.assertEqual(unapply_patch(new, patch), old,
                             msg=f"unapply: {new!r} -> {old!r}")


class ParseTest(unittest.TestCase):
    def test_parse_counts(self):
        patch = unified_diff("a\nb\nc\n", "a\nB\nc\n")
        hunks = parse_patch(patch)
        self.assertEqual(len(hunks), 1)
        hunk = hunks[0]
        self.assertEqual((hunk.old_start, hunk.old_count), (1, 3))
        self.assertEqual((hunk.new_start, hunk.new_count), (1, 3))


if __name__ == "__main__":
    unittest.main()
