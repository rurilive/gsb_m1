import io
import unittest

from jsonflow import JsonError, dump, load


class ArchiveReadTest(unittest.TestCase):
    def test_load_returns_same_shape_as_loads(self):
        doc = load(io.StringIO('{"a": 1, "b": [true, null], "c": "x"}'))
        self.assertEqual(doc, {"a": 1, "b": [True, None], "c": "x"})

    def test_load_accepts_bytes_stream(self):
        doc = load(io.BytesIO(b'{"n": 3, "m": 1.5}'))
        self.assertEqual(doc["n"], 3)
        self.assertEqual(doc["m"], 1.5)

    def test_load_reports_broken_document(self):
        with self.assertRaises(JsonError):
            load(io.StringIO('{"a": '))
        with self.assertRaises(JsonError):
            load(io.StringIO(""))


class ArchiveWriteTest(unittest.TestCase):
    def test_dump_then_load(self):
        source = io.StringIO('{"n": 1, "f": 1.5, "s": "x", "b": false}')
        out = io.StringIO()
        dump(load(source), out)
        again = load(io.StringIO(out.getvalue()))
        self.assertEqual(again, {"n": 1, "f": 1.5, "s": "x", "b": False})

    def test_dump_of_fresh_objects(self):
        out = io.StringIO()
        dump({"items": [1, 2, 3], "total": 6}, out)
        self.assertEqual(load(io.StringIO(out.getvalue())), {"items": [1, 2, 3], "total": 6})


if __name__ == "__main__":
    unittest.main()
