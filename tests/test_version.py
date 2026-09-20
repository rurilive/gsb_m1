"""parse_version / compare 现有行为的锁定测试。"""

import unittest

from verkit.version import Version, compare, parse_version


class TestParseVersion(unittest.TestCase):
    def test_plain(self):
        v = parse_version("1.2.3")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))
        self.assertIsNone(v.prerelease)
        self.assertIsNone(v.build)

    def test_prerelease_and_build(self):
        v = parse_version("2.0.0-rc.1+build.5")
        self.assertEqual(v.prerelease, "rc.1")
        self.assertEqual(v.build, "build.5")

    def test_str_roundtrip(self):
        for s in ("1.2.3", "0.0.0", "1.0.0-alpha.1", "2.0.0-rc.1+build.5"):
            self.assertEqual(str(parse_version(s)), s)

    def test_reject_partial(self):
        for s in ("1.2", "1", "1.2.3.4", ""):
            with self.assertRaises(ValueError):
                parse_version(s)

    def test_reject_leading_zero(self):
        with self.assertRaises(ValueError):
            parse_version("01.2.3")

    def test_reject_v_prefix_and_spaces(self):
        for s in ("v1.2.3", " 1.2.3", "1.2.3 "):
            with self.assertRaises(ValueError):
                parse_version(s)

    def test_reject_dangling_parts(self):
        for s in ("1.2.3-", "1.2.3+", "1.2.3-alpha..1", "1.2.3-alpha+", "1.2.3-01"):
            with self.assertRaises(ValueError):
                parse_version(s)

    def test_reject_non_string(self):
        with self.assertRaises(ValueError):
            parse_version(123)


class TestCompare(unittest.TestCase):
    def test_ordering_basic(self):
        self.assertEqual(compare("1.2.3", "1.2.3"), 0)
        self.assertEqual(compare("1.2.3", "1.2.4"), -1)
        self.assertEqual(compare("1.10.0", "1.9.9"), 1)

    def test_field_weight(self):
        self.assertEqual(compare("2.0.0", "10.0.0"), -1)
        self.assertEqual(compare("1.1.0", "1.0.9"), 1)

    def test_release_above_prerelease(self):
        self.assertEqual(compare("1.0.0", "1.0.0-alpha"), 1)

    def test_spec_example_chain(self):
        chain = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        for a, b in zip(chain, chain[1:]):
            self.assertEqual(compare(a, b), -1, f"期望 {a} < {b}")

    def test_numeric_identifier_below_alpha(self):
        self.assertEqual(compare("1.0.0-1", "1.0.0-alpha"), -1)

    def test_longer_identifier_set_wins(self):
        self.assertEqual(compare("1.0.0-alpha", "1.0.0-alpha.1"), -1)

    def test_build_metadata_ignored(self):
        self.assertEqual(compare("1.0.0+a", "1.0.0+b"), 0)
        self.assertEqual(compare("1.0.0+a", "1.0.0"), 0)

    def test_accepts_version_objects(self):
        self.assertEqual(
            compare(parse_version("1.2.3"), parse_version("1.2.4")), -1
        )

    def test_invalid_input_raises(self):
        with self.assertRaises(ValueError):
            compare("1.2", "1.0.0")


class TestVersionObject(unittest.TestCase):
    def test_ordering_dunders(self):
        self.assertLess(parse_version("1.0.0-rc.1"), parse_version("1.0.0"))
        self.assertGreater(parse_version("2.0.0"), parse_version("1.9.9"))
        self.assertLessEqual(parse_version("1.0.0+a"), parse_version("1.0.0+b"))

    def test_sorting_mixed_prerelease(self):
        items = [parse_version(s) for s in ("1.0.0", "1.0.0-rc.1", "0.9.0")]
        self.assertEqual(
            [str(v) for v in sorted(items)],
            ["0.9.0", "1.0.0-rc.1", "1.0.0"],
        )

    def test_eq_ignores_build(self):
        self.assertEqual(parse_version("1.0.0+a"), parse_version("1.0.0+b"))
        self.assertNotEqual(parse_version("1.0.0-a"), parse_version("1.0.0-b"))

    def test_constructor_rejects_bad_core(self):
        with self.assertRaises(ValueError):
            Version(1, -1, 0)
        with self.assertRaises(ValueError):
            Version("1", 0, 0)


if __name__ == "__main__":
    unittest.main()
