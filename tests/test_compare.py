"""deltafy 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from deltafy.compare import LineDiff
from deltafy import LineDiff as ExportedLineDiff


class TestLineDiff(unittest.TestCase):
    def test_identical_text_all_same(self):
        text = "alpha\nbeta\ngamma"
        diff = LineDiff(text, text)
        self.assertEqual(
            diff.operations(),
            [("same", 1, "alpha", "alpha"),
             ("same", 2, "beta", "beta"),
             ("same", 3, "gamma", "gamma")],
        )
        self.assertEqual(diff.changed_count(), 0)
        self.assertEqual(diff.same_count(), 3)

    def test_same_length_replace_records_positional(self):
        diff = LineDiff("alpha\nbeta\ngamma", "alpha\nBETA\ngamma")
        self.assertEqual(
            diff.operations(),
            [("same", 1, "alpha", "alpha"),
             ("replace", 2, "beta", "BETA"),
             ("same", 3, "gamma", "gamma")],
        )
        self.assertEqual(diff.changed_count(), 1)

    def test_new_shorter_pads_with_none(self):
        diff = LineDiff("alpha\nbeta\ngamma", "alpha\nbeta")
        ops = diff.operations()
        self.assertEqual(ops[0], ("same", 1, "alpha", "alpha"))
        self.assertEqual(ops[1], ("same", 2, "beta", "beta"))
        self.assertEqual(ops[2], ("replace", 3, "gamma", None))
        self.assertEqual(diff.changed_count(), 1)

    def test_new_longer_pads_with_none(self):
        diff = LineDiff("alpha", "alpha\nbeta")
        ops = diff.operations()
        self.assertEqual(ops[0], ("same", 1, "alpha", "alpha"))
        self.assertEqual(ops[1], ("replace", 2, None, "beta"))

    def test_empty_text(self):
        diff = LineDiff("", "")
        self.assertEqual(diff.operations(), [])
        self.assertEqual(diff.changed_count(), 0)

    def test_package_exports_line_diff(self):
        self.assertIs(ExportedLineDiff, LineDiff)


if __name__ == "__main__":
    unittest.main()
