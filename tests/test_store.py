"""Store 现有语义的锁定测试。"""

import json
import os
import tempfile
import threading
import unittest

from mvstore.store import Store


class TestStore(unittest.TestCase):
    def test_put_get_delete(self):
        s = Store()
        s.put("a", {"n": 1})
        self.assertEqual(s.get("a"), {"n": 1})
        self.assertTrue(s.delete("a"))
        self.assertIsNone(s.get("a"))

    def test_get_missing_returns_none(self):
        s = Store()
        self.assertIsNone(s.get("nope"))

    def test_delete_missing_returns_false(self):
        s = Store()
        self.assertFalse(s.delete("ghost"))

    def test_put_overwrites(self):
        s = Store()
        s.put("k", 1)
        s.put("k", 2)
        self.assertEqual(s.get("k"), 2)

    def test_json_values(self):
        s = Store()
        s.put("list", [1, 2, 3])
        s.put("s", "中文")
        s.put("d", {"x": [True, None, 1.5]})
        self.assertEqual(s.get("list"), [1, 2, 3])
        self.assertEqual(s.get("s"), "中文")
        self.assertEqual(s.get("d"), {"x": [True, None, 1.5]})

    def test_open_nonexistent_path_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "fresh.log")
            s = Store(path)
            self.assertIsNone(s.get("a"))
            s.put("a", 1)
            self.assertTrue(os.path.exists(path))

    def test_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "store.log")
            s = Store(path)
            s.put("a", 1)
            s.put("b", {"x": [True, None]})
            s.delete("a")
            s2 = Store(path)
            self.assertIsNone(s2.get("a"))
            self.assertEqual(s2.get("b"), {"x": [True, None]})

    def test_log_is_json_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "store.log")
            s = Store(path)
            s.put("a", 1)
            s.delete("a")
            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["op"], "put")
            self.assertEqual(lines[0]["key"], "a")
            self.assertEqual(lines[1]["op"], "del")
            self.assertEqual(lines[1]["key"], "a")

    def test_multithread_smoke(self):
        s = Store()

        def worker(i):
            for j in range(50):
                s.put("k%d" % (j % 5), i * 1000 + j)
                s.get("k%d" % (j % 5))

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for j in range(5):
            self.assertIsNotNone(s.get("k%d" % j))


if __name__ == "__main__":
    unittest.main()
