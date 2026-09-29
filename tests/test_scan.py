"""seekr 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from seekr.scan import Corpus


def build_corpus():
    c = Corpus()
    c.add("a", "the quick brown fox")
    c.add("b", "quick quick brown bear")
    c.add("c", "lazy dogs sleep")
    return c


class TestCorpus(unittest.TestCase):
    def test_add_returns_doc_id(self):
        c = Corpus()
        self.assertEqual(c.add("a", "hello"), "a")

    def test_add_rejects_empty_id(self):
        c = Corpus()
        with self.assertRaises(ValueError):
            c.add("", "hello")

    def test_add_rejects_non_str_id(self):
        c = Corpus()
        with self.assertRaises(ValueError):
            c.add(7, "hello")

    def test_add_rejects_non_str_text(self):
        c = Corpus()
        with self.assertRaises(ValueError):
            c.add("a", 7)

    def test_duplicate_doc_rejected(self):
        c = build_corpus()
        with self.assertRaises(ValueError):
            c.add("a", "other")

    def test_len_and_contains(self):
        c = build_corpus()
        self.assertEqual(len(c), 3)
        self.assertIn("b", c)
        self.assertNotIn("z", c)

    def test_doc_ids_in_insertion_order(self):
        c = build_corpus()
        self.assertEqual(c.doc_ids(), ("a", "b", "c"))

    def test_doc_ids_returns_tuple(self):
        c = build_corpus()
        self.assertIsInstance(c.doc_ids(), tuple)

    def test_text_roundtrip(self):
        c = build_corpus()
        self.assertEqual(c.text("c"), "lazy dogs sleep")

    def test_text_missing_doc(self):
        c = build_corpus()
        with self.assertRaises(KeyError):
            c.text("z")

    def test_search_hits_in_doc_order(self):
        c = build_corpus()
        self.assertEqual(c.search("brown"), ["a", "b"])

    def test_search_case_sensitive(self):
        c = build_corpus()
        self.assertEqual(c.search("Quick"), [])

    def test_search_is_substring_not_word(self):
        c = build_corpus()
        self.assertEqual(c.search("ick"), ["a", "b"])

    def test_search_no_hit_is_empty(self):
        c = build_corpus()
        self.assertEqual(c.search("zebra"), [])

    def test_search_empty_needle_rejected(self):
        c = build_corpus()
        with self.assertRaises(ValueError):
            c.search("")

    def test_search_non_str_needle_rejected(self):
        c = build_corpus()
        with self.assertRaises(ValueError):
            c.search(None)

    def test_count_repeated_occurrences(self):
        c = build_corpus()
        self.assertEqual(c.count("quick"), 3)

    def test_count_no_hit_is_zero(self):
        c = build_corpus()
        self.assertEqual(c.count("zebra"), 0)

    def test_count_empty_needle_rejected(self):
        c = build_corpus()
        with self.assertRaises(ValueError):
            c.count("")

    def test_count_non_str_needle_rejected(self):
        c = build_corpus()
        with self.assertRaises(ValueError):
            c.count(1)

    def test_remove_drops_doc(self):
        c = build_corpus()
        c.remove("b")
        self.assertEqual(len(c), 2)
        self.assertEqual(c.doc_ids(), ("a", "c"))
        self.assertEqual(c.search("quick"), ["a"])
        self.assertNotIn("b", c)

    def test_remove_missing_doc(self):
        c = build_corpus()
        with self.assertRaises(KeyError):
            c.remove("z")

    def test_remove_then_readd_allowed(self):
        c = build_corpus()
        c.remove("a")
        c.add("a", "fresh text")
        self.assertEqual(c.text("a"), "fresh text")
        self.assertEqual(c.search("fresh"), ["a"])


if __name__ == "__main__":
    unittest.main()