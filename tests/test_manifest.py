"""清单解析与版本工具的既有行为锁定。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from replug.errors import ManifestError  # noqa: E402
from replug.manifest import compare_versions, parse_manifest, parse_version  # noqa: E402


class VersionTest(unittest.TestCase):
    def test_parse_version_splits_three_numbers(self):
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("10.0.20"), (10, 0, 20))

    def test_bad_versions_are_rejected(self):
        for bad in ("1.2", "1.2.3.4", "v1.2.3", "1.2.x", "", None, 1.2, True):
            with self.assertRaises(ManifestError):
                parse_version(bad)

    def test_compare_versions_orders_numerically(self):
        self.assertEqual(compare_versions("1.2.3", "1.2.3"), 0)
        self.assertEqual(compare_versions("1.2.3", "1.10.0"), -1)
        self.assertEqual(compare_versions("2.0.0", "1.9.9"), 1)
        self.assertEqual(compare_versions("0.1.0", "0.1.1"), -1)


class ManifestParseTest(unittest.TestCase):
    def test_minimal_manifest_is_accepted(self):
        manifest = parse_manifest({"name": "alpha", "version": "1.0.0"},
                                  "alpha", "alpha.py")
        self.assertEqual(manifest.name, "alpha")
        self.assertEqual(manifest.version, "1.0.0")
        self.assertEqual(manifest.description, "")
        self.assertIn("alpha", repr(manifest))

    def test_description_is_optional_and_kept(self):
        manifest = parse_manifest({"name": "a", "version": "2.0.0",
                                   "description": "干活的"}, "a", "a.py")
        self.assertEqual(manifest.description, "干活的")

    def test_non_dict_manifest_is_rejected(self):
        for bad in (None, [], "PLUGIN"):
            with self.assertRaises(ManifestError):
                parse_manifest(bad, "a", "a.py")

    def test_missing_name_or_version_is_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"version": "1.0.0"}, "a", "a.py")
        with self.assertRaises(ManifestError):
            parse_manifest({"name": "a"}, "a", "a.py")

    def test_name_must_match_file_stem(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"name": "beta", "version": "1.0.0"}, "alpha", "alpha.py")

    def test_bad_version_in_manifest_is_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"name": "a", "version": "1.0"}, "a", "a.py")

    def test_non_string_description_is_rejected(self):
        with self.assertRaises(ManifestError):
            parse_manifest({"name": "a", "version": "1.0.0", "description": 7},
                           "a", "a.py")


if __name__ == "__main__":
    unittest.main()
