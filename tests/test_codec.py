"""codec 现有行为的锁定测试。"""

import json
import os
import tempfile
import unittest

from dedupkit import codec
from dedupkit.ledger import Ledger


class TestCodec(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "ledger.json")

    def write_raw(self, text):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def read_raw(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_roundtrip_string_keys(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        ledger.add("a", "u2")
        ledger.add("b", "u3")
        codec.save(ledger, self.path)
        back = codec.load(self.path)
        self.assertEqual(back.names(), ("a", "b"))
        self.assertEqual(set(back.keys("a")), {"u1", "u2"})
        self.assertEqual(back.total(), 3)

    def test_roundtrip_mixed_key_types(self):
        ledger = Ledger()
        keys = ["u1", 7, b"raw", (1, "two"), None]
        for key in keys:
            ledger.add("a", key)
        codec.save(ledger, self.path)
        back = codec.load(self.path)
        self.assertEqual(set(back.keys("a")), set(keys))

    def test_bool_key_stays_bool(self):
        ledger = Ledger()
        ledger.add("a", True)
        codec.save(ledger, self.path)
        back = codec.load(self.path)
        (only,) = back.keys("a")
        self.assertIsInstance(only, bool)
        self.assertIs(only, True)

    def test_nested_tuple_keys_rebuild_as_tuples(self):
        ledger = Ledger()
        key = (b"x", (1, None), "y")
        ledger.add("a", key)
        codec.save(ledger, self.path)
        back = codec.load(self.path)
        (only,) = back.keys("a")
        self.assertEqual(only, key)
        self.assertIsInstance(only, tuple)
        self.assertIsInstance(only[1], tuple)
        self.assertIsInstance(only[0], bytes)

    def test_saving_twice_produces_identical_bytes(self):
        ledger = Ledger()
        for name in ["b", "a"]:
            for key in ["u2", "u1", 3]:
                ledger.add(name, key)
        codec.save(ledger, self.path)
        first = self.read_raw()
        codec.save(ledger, self.path)
        self.assertEqual(first, self.read_raw())

    def test_file_layout_is_sorted_and_versioned(self):
        ledger = Ledger()
        ledger.add("z", "u1")
        ledger.add("a", "u2")
        codec.save(ledger, self.path)
        document = json.loads(self.read_raw())
        self.assertEqual(document["fmt"], 1)
        self.assertEqual(list(document["shards"]), ["a", "z"])
        self.assertEqual(document["shards"]["z"], [["s", "u1"]])

    def test_empty_ledger_roundtrip(self):
        codec.save(Ledger(), self.path)
        back = codec.load(self.path)
        self.assertEqual(back.names(), ())
        self.assertEqual(back.total(), 0)

    def test_extra_unknown_fields_are_ignored(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        codec.save(ledger, self.path)
        document = json.loads(self.read_raw())
        document["note"] = "写文件的人多带了一点东西"
        self.write_raw(json.dumps(document))
        back = codec.load(self.path)
        self.assertEqual(set(back.keys("a")), {"u1"})

    def test_unknown_format_version_raises(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        codec.save(ledger, self.path)
        document = json.loads(self.read_raw())
        document["fmt"] = 99
        self.write_raw(json.dumps(document))
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_missing_fmt_raises(self):
        self.write_raw(json.dumps({"shards": {}}))
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_invalid_json_raises(self):
        self.write_raw("{not json")
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_non_object_toplevel_raises(self):
        self.write_raw("[1, 2, 3]")
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_shards_must_be_object(self):
        self.write_raw(json.dumps({"fmt": 1, "shards": []}))
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_unknown_key_tag_raises(self):
        self.write_raw(json.dumps({"fmt": 1, "shards": {"a": [["q", 1]]}}))
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_malformed_key_entry_raises(self):
        self.write_raw(json.dumps({"fmt": 1, "shards": {"a": [["s"]]}}))
        with self.assertRaises(ValueError):
            codec.load(self.path)

    def test_unsupported_key_type_on_save_raises(self):
        ledger = Ledger()
        ledger.add("a", 1.5)
        with self.assertRaises(ValueError):
            codec.save(ledger, self.path)

    def test_save_rejects_non_ledger(self):
        with self.assertRaises(TypeError):
            codec.save({"a": ["u1"]}, self.path)

    def test_missing_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            codec.load(os.path.join(self._tmp.name, "absent.json"))


if __name__ == "__main__":
    unittest.main()
