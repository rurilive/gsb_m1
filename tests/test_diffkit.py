"""diffkit 防回归测试：覆盖发布群/值班记录里报过的四类缺陷。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v
或直接：
    python3 tests/test_diffkit.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diffkit import apply_patch, parse_patch, unapply_patch, unified_diff


def roundtrip(old, new, context=3):
    """old -> diff -> apply 得 new；new -> unapply 还原 old。"""
    patch = unified_diff(old, new, context=context)
    assert apply_patch(old, patch) == new, (old, new, patch)
    assert unapply_patch(new, patch) == old, (old, new, patch)
    return patch


class TestRepeatedLinesOffset(unittest.TestCase):
    """现象 1：重复行文件上打补丁，落点偏一行。"""

    def test_change_lands_on_correct_line(self):
        old = "head\n" + "rate 100\n" * 10 + "tail\n"
        lines = ["head"] + ["rate 100"] * 10 + ["tail"]
        lines[5] = "rate 50"
        new = "\n".join(lines) + "\n"
        patch = unified_diff(old, new)
        applied = apply_patch(old, patch)
        self.assertEqual(applied, new)
        self.assertEqual(applied.splitlines()[5], "rate 50")
        self.assertEqual(applied.splitlines()[6], "rate 100")

    def test_hunk_header_is_one_based(self):
        # hunk 头 -3,3 是 1 基行号，应用时必须换算成 0 基下标 2
        patch = ("--- a\n+++ b\n"
                 "@@ -3,3 +3,3 @@\n"
                 " c\n"
                 "-d\n"
                 "+D\n"
                 " e\n")
        text = "a\nb\nc\nd\ne\nf\n"
        self.assertEqual(apply_patch(text, patch), "a\nb\nc\nD\ne\nf\n")
class TestTrailingNewline(unittest.TestCase):
    """现象 2：打完补丁文件尾换行丢失。"""

    def test_apply_preserves_trailing_newline(self):
        old = "a\nb\nc\n"
        new = "a\nB\nc\n"
        applied = apply_patch(old, unified_diff(old, new))
        self.assertEqual(applied, new)
        self.assertTrue(applied.endswith("\n"))

    def test_apply_preserves_missing_trailing_newline(self):
        old = "a\nb\nc"
        new = "a\nB\nc"
        applied = apply_patch(old, unified_diff(old, new))
        self.assertEqual(applied, new)
        self.assertFalse(applied.endswith("\n"))

    def test_newline_added_at_eof(self):
        roundtrip("a\nb", "a\nb\n")

    def test_newline_removed_at_eof(self):
        roundtrip("a\nb\n", "a\nb")

    def test_no_newline_marker_follows_its_own_line(self):
        # 旧文件无尾换行、新文件有：标记必须紧跟 '-' 行，而不是 hunk 末尾
        patch = unified_diff("a\nlast", "a\nlast\n")
        self.assertIn("-last\n\\ No newline at end of file\n+last\n", patch)
        self.assertEqual(apply_patch("a\nlast", patch), "a\nlast\n")
        self.assertEqual(unapply_patch("a\nlast\n", patch), "a\nlast")

    def test_delete_last_line_of_file_without_newline(self):
        roundtrip("a\nb", "a\n")

    def test_delete_to_empty_file(self):
        roundtrip("only\n", "")

    def test_unapply_restores_newline_when_deleted_to_empty(self):
        patch = unified_diff("only\n", "")
        self.assertEqual(unapply_patch("", patch), "only\n")


class TestBaselineMismatch(unittest.TestCase):
    """现象 3：补丁基线与目标不一致时必须报错，不允许静默产出。"""

    def test_context_mismatch_raises(self):
        base = "\n".join(f"entry-{i} = ok" for i in range(1, 13)) + "\n"
        patched = base.replace("entry-2 = ok", "entry-2 = changed")
        patched = patched.replace("entry-11 = ok", "entry-11 = changed")
        patch = unified_diff(base, patched)
        drifted = base.replace("entry-11 = ok", "entry-11 = edited")
        with self.assertRaises(ValueError):
            apply_patch(drifted, patch)

    def test_no_partial_result_on_mismatch(self):
        # 前一个 hunk 能匹配、后一个不匹配时，也必须整体报错
        base = "\n".join(f"line-{i}" for i in range(1, 21)) + "\n"
        patched = base.replace("line-2", "line-2x").replace("line-19", "line-19x")
        patch = unified_diff(base, patched)
        drifted = base.replace("line-19", "line-19-other")
        with self.assertRaises(ValueError):
            apply_patch(drifted, patch)

    def test_unapply_mismatch_raises(self):
        patch = unified_diff("a\nb\n", "a\nb\nc\n")
        with self.assertRaises(ValueError):
            unapply_patch("a\nX\nc\n", patch)


class TestUnapply(unittest.TestCase):
    """现象 4：反向应用（回滚）。"""

    def test_unapply_appended_line(self):
        patch = unified_diff("alpha\nbeta\n", "alpha\nbeta\ngamma\n")
        self.assertEqual(unapply_patch("alpha\nbeta\ngamma\n", patch),
                         "alpha\nbeta\n")

    def test_unapply_uses_new_side_coordinates(self):
        # 新旧两侧行数不同的 hunk，回滚必须按新侧区间定位
        old = "one\ntwo\nthree\n"
        new = "one\ninserted\ntwo\nthree\n"
        patch = unified_diff(old, new)
        self.assertEqual(unapply_patch(new, patch), old)

    def test_unapply_pure_insertion_at_start(self):
        old = "a\nb\n"
        new = "x\na\nb\n"
        patch = unified_diff(old, new, context=0)
        self.assertEqual(apply_patch(old, patch), new)
        self.assertEqual(unapply_patch(new, patch), old)


class TestRoundtripMatrix(unittest.TestCase):
    """生成-应用-回滚全链路矩阵。"""

    CASES = [
        ("", "x\n"),
        ("x\n", ""),
        ("", ""),
        ("a\n", "a\nb\n"),
        ("a\nb\n", "a\n"),
        ("x\na\nb\n", "a\nb\n"),
        ("a\nb\n", "x\na\nb\n"),
        ("a\nb\nc\n", "a\nX\nc\n"),
        ("a\nb\nc", "a\nX\nc"),
        ("a\nb\nc\n", "a\nb\nc"),
        ("a\nb\nc", "a\nb\nc\n"),
        ("same\n" * 20, "same\n" * 9 + "diff\n" + "same\n" * 10),
        ("\n".join(f"l{i}" for i in range(30)) + "\n",
         "\n".join(f"l{i}" if i not in (3, 25) else f"L{i}"
                   for i in range(30)) + "\n"),
    ]

    def test_roundtrips(self):
        for old, new in self.CASES:
            with self.subTest(old=old, new=new):
                roundtrip(old, new)

    def test_roundtrips_zero_context(self):
        for old, new in self.CASES:
            with self.subTest(old=old, new=new):
                roundtrip(old, new, context=0)

    def test_no_diff_returns_empty_patch(self):
        self.assertEqual(unified_diff("a\nb\n", "a\nb\n"), "")
        self.assertEqual(apply_patch("a\nb\n", ""), "a\nb\n")
        self.assertEqual(unapply_patch("a\nb\n", ""), "a\nb\n")

    def test_newline_only_change_produces_patch(self):
        patch = unified_diff("a\nb", "a\nb\n")
        self.assertNotEqual(patch, "")
        self.assertEqual(apply_patch("a\nb", patch), "a\nb\n")


class TestParsePatch(unittest.TestCase):
    def test_counts_default_to_one(self):
        hunks = parse_patch("@@ -3 +4 @@\n-a\n+b\n")
        self.assertEqual((hunks[0].old_count, hunks[0].new_count), (1, 1))

    def test_zero_count_range(self):
        hunks = parse_patch("@@ -0,0 +1 @@\n+x\n")
        self.assertEqual((hunks[0].old_start, hunks[0].old_count), (0, 0))

    def test_no_newline_marker_recorded(self):
        hunks = parse_patch("@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b\n")
        self.assertEqual(hunks[0].no_newline, "-")

    def test_bad_hunk_header_raises(self):
        with self.assertRaises(ValueError):
            parse_patch("@@ 这不是合法头 @@\n")


if __name__ == "__main__":
    unittest.main()
