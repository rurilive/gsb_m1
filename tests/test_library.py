"""DocLibrary 的基线行为测试。"""

import unittest

from docbase.library import DocLibrary


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.lib = DocLibrary()

    def test_add_returns_whether_new(self):
        self.assertTrue(self.lib.add("d1", "支付超时"))
        self.assertFalse(self.lib.add("d1", "支付超时了"))
        self.assertEqual(self.lib.count(), 1)

    def test_add_rejects_bad_arguments(self):
        with self.assertRaises(ValueError):
            self.lib.add("", "text")
        with self.assertRaises(ValueError):
            self.lib.add(3, "text")
        with self.assertRaises(ValueError):
            self.lib.add("d1", None)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.lib.get("nope"))
        self.lib.add("d1", "abc")
        self.assertEqual(self.lib.get("d1"), "abc")

    def test_remove_returns_whether_present(self):
        self.lib.add("d1", "abc")
        self.assertTrue(self.lib.remove("d1"))
        self.assertFalse(self.lib.remove("d1"))
        self.assertIsNone(self.lib.get("d1"))

    def test_ids_scan_and_count(self):
        self.lib.add("b", "two")
        self.lib.add("a", "one")
        self.lib.add("c", "three")
        self.assertEqual(self.lib.ids(), ["a", "b", "c"])
        self.assertEqual(self.lib.count(), 3)
        self.assertEqual(
            self.lib.scan(),
            [("a", "one"), ("b", "two"), ("c", "three")],
        )

    def test_search_exact_match_sorted(self):
        self.lib.add("b", "gateway timeout")
        self.lib.add("a", "timeout on gateway")
        self.lib.add("c", "gateway ok")
        self.assertEqual(self.lib.search("timeout"), ["a", "b"])
        self.assertEqual(self.lib.search("GATEWAY"), ["a", "b", "c"])

    def test_search_requires_all_tokens(self):
        self.lib.add("d1", "gateway timeout")
        self.lib.add("d2", "gateway only")
        self.assertEqual(self.lib.search("gateway timeout"), ["d1"])

    def test_search_cjk_is_per_char(self):
        self.lib.add("d1", "支付超时排查")
        self.lib.add("d2", "回调丢失")
        self.assertEqual(self.lib.search("支付"), ["d1"])
        self.assertEqual(self.lib.search("超"), ["d1"])
        self.assertEqual(self.lib.search("丢失"), ["d2"])

    def test_search_empty_term_returns_nothing(self):
        self.lib.add("d1", "abc")
        self.assertEqual(self.lib.search(""), [])
        self.assertEqual(self.lib.search("  ，。"), [])
        self.assertEqual(self.lib.stats()["searches"], 0)

    def test_stats_counters(self):
        self.lib.add("d1", "abc")
        self.lib.add("d1", "abcd")
        self.lib.remove("d1")
        self.lib.remove("d1")
        self.assertEqual(self.lib.stats()["adds"], 2)
        self.assertEqual(self.lib.stats()["removes"], 1)
        self.assertEqual(self.lib.stats()["docs"], 0)

    def test_subscribe_sees_add_replace_and_remove(self):
        seen = []
        self.lib.subscribe(lambda doc_id, old, new: seen.append((doc_id, old, new)))
        self.lib.add("d1", "one")
        self.lib.add("d1", "two")
        self.lib.remove("d1")
        self.assertEqual(
            seen,
            [("d1", None, "one"), ("d1", "one", "two"), ("d1", "two", None)],
        )

    def test_remove_missing_does_not_notify(self):
        seen = []
        self.lib.subscribe(lambda doc_id, old, new: seen.append(doc_id))
        self.assertFalse(self.lib.remove("nope"))
        self.assertEqual(seen, [])

    def test_unsubscribe_stops_calls(self):
        seen = []
        cb = lambda doc_id, old, new: seen.append(doc_id)  # noqa: E731
        self.lib.subscribe(cb)
        self.lib.add("d1", "one")
        self.lib.unsubscribe(cb)
        self.lib.add("d2", "two")
        self.lib.unsubscribe(cb)  # 再摘一次也不报错
        self.assertEqual(seen, ["d1"])

    def test_subscriber_snapshot_survives_mutation(self):
        calls = []

        def first(doc_id, old, new):
            calls.append(doc_id)
            self.lib.unsubscribe(second)

        def second(doc_id, old, new):
            calls.append("second")

        self.lib.subscribe(first)
        self.lib.subscribe(second)
        self.lib.add("d1", "one")
        self.assertEqual(calls, ["d1", "second"])
        self.lib.add("d2", "two")
        self.assertEqual(calls, ["d1", "second", "d2"])


if __name__ == "__main__":
    unittest.main()
