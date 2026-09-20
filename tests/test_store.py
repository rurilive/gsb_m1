"""IndexStore 行为基线：现有语义锁死，重构后原样全绿。"""
import os
import shutil
import tempfile
import unittest

from idxstore import SNAPSHOT_NAME, IndexStore, tokenize


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="idxstore-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _store(self, **kw):
        return IndexStore(self.dir, **kw)


class TestQuery(StoreTest):
    def test_get_returns_stored_text(self):
        s = self._store()
        s.put("d1", "quick brown fox")
        self.assertEqual(s.get("d1"), "quick brown fox")

    def test_get_missing_is_none(self):
        self.assertIsNone(self._store().get("nope"))

    def test_search_returns_sorted_doc_ids(self):
        s = self._store()
        s.put("d3", "fox")
        s.put("d1", "fox")
        s.put("d2", "fox")
        self.assertEqual(s.search("fox"), ["d1", "d2", "d3"])

    def test_search_is_case_insensitive(self):
        s = self._store()
        s.put("d1", "Quick FOX")
        self.assertEqual(s.search("fOx"), ["d1"])

    def test_search_unknown_term_is_empty(self):
        self.assertEqual(self._store().search("ghost"), [])

    def test_doc_count(self):
        s = self._store()
        s.put("d1", "a")
        s.put("d2", "b")
        self.assertEqual(s.doc_count(), 2)


class TestMutation(StoreTest):
    def test_put_same_id_reindexes(self):
        s = self._store()
        s.put("d1", "alpha beta")
        s.put("d1", "beta gamma")
        self.assertEqual(s.search("alpha"), [])
        self.assertEqual(s.search("gamma"), ["d1"])
        self.assertEqual(s.get("d1"), "beta gamma")
        self.assertEqual(s.doc_count(), 1)

    def test_delete_removes_from_index(self):
        s = self._store()
        s.put("d1", "alpha beta")
        s.delete("d1")
        self.assertIsNone(s.get("d1"))
        self.assertEqual(s.search("alpha"), [])

    def test_delete_missing_is_noop(self):
        s = self._store()
        s.put("d1", "alpha")
        s.delete("nope")
        self.assertEqual(s.doc_count(), 1)
        self.assertEqual(s.search("alpha"), ["d1"])

    def test_tokenize_lowercases_and_dedupes(self):
        self.assertEqual(tokenize("Fox fox DOG"), ["dog", "fox"])


class TestSnapshot(StoreTest):
    def test_snapshot_then_load_restores_state(self):
        s = self._store()
        s.put("d1", "quick brown fox")
        s.put("d2", "lazy dog")
        s.delete("d1")
        s.snapshot()

        reopened = self._store()
        self.assertEqual(reopened.load(), 1)
        self.assertEqual(reopened.search("dog"), ["d2"])
        self.assertEqual(reopened.search("fox"), [])
        self.assertEqual(reopened.doc_count(), 1)

    def test_load_without_snapshot_returns_zero(self):
        self.assertEqual(self._store().load(), 0)

    def test_auto_snapshot_at_threshold(self):
        s = self._store(snapshot_every=3)
        for i in range(3):
            s.put("d%d" % i, "term%d" % i)
        self.assertTrue(os.path.exists(os.path.join(self.dir, SNAPSHOT_NAME)))

    def test_snapshot_file_is_single_file(self):
        s = self._store()
        s.put("d1", "alpha")
        s.snapshot()
        entries = sorted(os.listdir(self.dir))
        self.assertEqual(entries, [SNAPSHOT_NAME])


if __name__ == "__main__":
    unittest.main()
