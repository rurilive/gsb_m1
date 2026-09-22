"""切分口径的基线测试。"""

import unittest

from docbase.text import chunks, is_cjk, tokens


class ChunksTest(unittest.TestCase):
    def test_mixed_text_splits_by_script(self):
        self.assertEqual(
            chunks("重启 gateway 服务"),
            [("cjk", "重启"), ("other", " gateway "), ("cjk", "服务")],
        )

    def test_punctuation_breaks_cjk_runs(self):
        self.assertEqual(
            chunks("苹果，香蕉"),
            [("cjk", "苹果"), ("other", "，"), ("cjk", "香蕉")],
        )

    def test_pure_latin(self):
        self.assertEqual(chunks("retry 3 times"), [("other", "retry 3 times")])

    def test_empty_text(self):
        self.assertEqual(chunks(""), [])

    def test_is_cjk_boundaries(self):
        self.assertTrue(is_cjk("中"))
        self.assertTrue(is_cjk("齄"))
        self.assertFalse(is_cjk("a"))
        self.assertFalse(is_cjk("，"))
        self.assertFalse(is_cjk(" "))
        self.assertFalse(is_cjk("3"))


class TokensTest(unittest.TestCase):
    def test_latin_casefolded_and_split(self):
        self.assertEqual(tokens("Export Timeout-3"), ["export", "timeout", "3"])

    def test_cjk_takes_single_chars(self):
        self.assertEqual(tokens("支付超时"), ["支", "付", "超", "时"])

    def test_mixed_text(self):
        self.assertEqual(
            tokens("重启 gateway 服务"), ["重", "启", "gateway", "服", "务"]
        )

    def test_punctuation_dropped(self):
        self.assertEqual(tokens("a,b。c！"), ["a", "b", "c"])

    def test_empty_and_punctuation_only(self):
        self.assertEqual(tokens(""), [])
        self.assertEqual(tokens("  ，。！ "), [])


if __name__ == "__main__":
    unittest.main()
