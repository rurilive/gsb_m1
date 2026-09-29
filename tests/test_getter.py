"""基线测试：锁住 Getter 现在的点号取值行为，一字不改。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pather import Getter


DOC = {
    "user": {
        "name": "ann",
        "age": 30,
        "address": {"city": "beijing", "zip": "100000"},
    },
    "tags": ["a", "b"],
}


class GetterBaselineTest(unittest.TestCase):
    def setUp(self):
        self.getter = Getter(DOC)

    def test_single_level(self):
        self.assertEqual(self.getter.get("tags"), ["a", "b"])

    def test_multi_level(self):
        self.assertEqual(self.getter.get("user.address.city"), "beijing")

    def test_missing_key_returns_none(self):
        self.assertEqual(self.getter.get("user.missing"), None)

    def test_missing_intermediate_returns_none(self):
        self.assertEqual(self.getter.get("user.missing.deep"), None)

    def test_non_dict_midway_returns_none(self):
        self.assertEqual(self.getter.get("tags.0"), None)

    def test_empty_path_returns_root(self):
        self.assertIs(self.getter.get(""), DOC)

    def test_non_string_path_raises(self):
        with self.assertRaises(TypeError):
            self.getter.get(123)


if __name__ == "__main__":
    unittest.main()
