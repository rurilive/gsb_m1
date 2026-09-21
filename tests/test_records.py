import unittest

from logpipe.records import check_record, clone, dumps, is_leaf, loads


class CheckRecordTests(unittest.TestCase):
    def test_rejects_non_dicts(self):
        for bad in [None, 5, "text", ["a"]]:
            with self.subTest(value=bad):
                with self.assertRaises(TypeError):
                    check_record(bad)

    def test_accepts_dict(self):
        record = {"a": 1}
        self.assertIs(check_record(record), record)


class CloneTests(unittest.TestCase):
    def test_clone_is_independent(self):
        record = {"user": {"name": "amy"}, "tags": ["a"]}
        copy = clone(record)
        copy["user"]["name"] = "bob"
        copy["tags"].append("b")
        self.assertEqual(record, {"user": {"name": "amy"}, "tags": ["a"]})

    def test_clone_keeps_cycles(self):
        record = {"name": "root"}
        record["self"] = record
        copy = clone(record)
        self.assertIs(copy["self"], copy)
        self.assertEqual(copy["name"], "root")


class SerializationTests(unittest.TestCase):
    def test_line_is_deterministic(self):
        self.assertEqual(dumps({"b": 1, "a": 2}), '{"a":2,"b":1}')
        self.assertEqual(dumps({"a": 2, "b": 1}), dumps({"b": 1, "a": 2}))

    def test_unicode_is_kept_readable(self):
        self.assertEqual(dumps({"city": "北京"}), '{"city":"北京"}')

    def test_round_trip(self):
        record = {"user": {"phone": "13812345678"}, "flags": [True, None], "n": 1.5}
        self.assertEqual(loads(dumps(record)), record)

    def test_empty_record(self):
        self.assertEqual(dumps({}), "{}")


class IsLeafTests(unittest.TestCase):
    def test_scalars_are_leaves(self):
        for value in [None, True, 0, 1.5, "x"]:
            self.assertTrue(is_leaf(value))

    def test_containers_are_not_leaves(self):
        self.assertFalse(is_leaf({}))
        self.assertFalse(is_leaf([]))


if __name__ == "__main__":
    unittest.main()
