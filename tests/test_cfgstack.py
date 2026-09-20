"""cfgstack 行为清单——重构期间一个字都不改，必须原样全绿。"""

import json
import os
import tempfile
import unittest
from unittest import mock

from cfgstack import (
    ConfigStack,
    MissingKeyError,
    load_config,
    merge_dicts,
    merge_profiles,
    required_subset,
)

DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 80, "timeout": 30},
    "log": {"level": "info"},
}
FILE_LAYER = {
    "server": {"port": 8080},
    "features": {"beta": True},
}


def make_stack():
    s = ConfigStack()
    s.add_layer("defaults", DEFAULTS)
    s.add_layer("file", FILE_LAYER)
    return s


class TestMergeDicts(unittest.TestCase):
    def test_deep_merge_keeps_siblings(self):
        out = merge_dicts({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}})
        self.assertEqual(out, {"a": {"x": 1, "y": 3}})

    def test_scalar_overrides_dict(self):
        self.assertEqual(merge_dicts({"a": {"x": 1}}, {"a": 5}), {"a": 5})

    def test_dict_overrides_scalar(self):
        self.assertEqual(merge_dicts({"a": 5}, {"a": {"x": 1}}), {"a": {"x": 1}})

    def test_inputs_not_mutated(self):
        a = {"a": {"x": 1}}
        b = {"a": {"y": 2}, "b": 1}
        merge_dicts(a, b)
        self.assertEqual(a, {"a": {"x": 1}})
        self.assertEqual(b, {"a": {"y": 2}, "b": 1})

    def test_three_levels(self):
        out = merge_dicts({"a": {"b": {"c": 1}}}, {"a": {"b": {"d": 2}}})
        self.assertEqual(out, {"a": {"b": {"c": 1, "d": 2}}})


class TestMergeProfiles(unittest.TestCase):
    def test_chain_of_overrides(self):
        out = merge_profiles({"a": {"x": 1}}, {"a": {"y": 2}}, {"a": {"x": 9}})
        self.assertEqual(out, {"a": {"x": 9, "y": 2}})

    def test_base_not_mutated(self):
        base = {"a": {"x": 1}}
        merge_profiles(base, {"a": {"x": 2}})
        self.assertEqual(base, {"a": {"x": 1}})

    def test_later_wins_scalar(self):
        self.assertEqual(merge_profiles({"p": 1}, {"p": 2}, {"p": 3}), {"p": 3})


class TestRequiredSubset(unittest.TestCase):
    def test_picks_keys(self):
        out = required_subset({"a": 1, "b": 2, "c": 3}, ["a", "c"], "prof")
        self.assertEqual(out, {"a": 1, "c": 3})

    def test_missing_message_exact(self):
        with self.assertRaises(MissingKeyError) as cm:
            required_subset({"a": 1}, ["zz"], "prof")
        self.assertEqual(str(cm.exception), "key 'zz' missing in prof")


class TestStackPrecedence(unittest.TestCase):
    def test_file_overrides_defaults_keeps_siblings(self):
        s = make_stack()
        self.assertEqual(s.get("server.port"), 8080)
        self.assertEqual(s.get("server.host"), "0.0.0.0")
        self.assertEqual(s.get("server.timeout"), 30)
        self.assertEqual(s.get("log.level"), "info")
        self.assertIs(s.get("features.beta"), True)

    def test_env_overrides_file(self):
        s = make_stack()
        with mock.patch.dict(os.environ, {"GW__server__timeout": "99"}):
            s.apply_env("GW")
        self.assertEqual(s.get("server.timeout"), "99")

    def test_env_value_stays_string(self):
        s = make_stack()
        with mock.patch.dict(os.environ, {"GW__server__port": "9090"}):
            s.apply_env("GW")
        self.assertIsInstance(s.get("server.port"), str)
        self.assertEqual(s.get("server.port"), "9090")

    def test_layers_order(self):
        s = make_stack()
        self.assertEqual(s.layers(), ["defaults", "file"])
        s.apply_env("GW")
        self.assertEqual(s.layers(), ["defaults", "file", "env"])

    def test_env_top_level_key(self):
        s = ConfigStack()
        with mock.patch.dict(os.environ, {"GW__debug": "on"}):
            s.apply_env("GW")
        self.assertEqual(s.get("debug"), "on")

    def test_env_ignores_other_prefix(self):
        s = ConfigStack()
        with mock.patch.dict(os.environ, {"OTHER__x": "1"}):
            s.apply_env("GW")
        self.assertEqual(s.as_dict(), {})

    def test_env_skips_empty_segments_and_bare_prefix(self):
        s = ConfigStack()
        env = {"GW__": "x", "GW__a__": "y", "GW": "z", "GW__b": "1"}
        with mock.patch.dict(os.environ, env):
            s.apply_env("GW")
        self.assertEqual(s.as_dict(), {"b": "1"})

    def test_add_layer_type_error_message(self):
        s = ConfigStack()
        with self.assertRaises(TypeError) as cm:
            s.add_layer("x", [1, 2])
        self.assertEqual(str(cm.exception), "layer x: expected dict, got list")

    def test_layers_recorded_even_when_empty(self):
        s = ConfigStack()
        s.add_layer("empty", {})
        self.assertEqual(s.layers(), ["empty"])


class TestStackAccessors(unittest.TestCase):
    def setUp(self):
        self.s = make_stack()

    def test_get_default(self):
        self.assertEqual(self.s.get("nope.x", "dflt"), "dflt")
        self.assertIsNone(self.s.get("server.nope"))

    def test_get_none_value_counts_as_found(self):
        s = ConfigStack()
        s.add_layer("d", {"a": None})
        self.assertIsNone(s.get("a", "dflt"))

    def test_require_found_and_missing(self):
        self.assertEqual(self.s.require("server.port"), 8080)
        with self.assertRaises(MissingKeyError) as cm:
            self.s.require("db.url")
        self.assertEqual(str(cm.exception), "missing key: db.url")

    def test_require_into_scalar_path(self):
        s = ConfigStack()
        s.add_layer("d", {"a": 5})
        with self.assertRaises(MissingKeyError) as cm:
            s.require("a.b")
        self.assertEqual(str(cm.exception), "missing key: a.b")

    def test_require_int_passthrough(self):
        self.assertEqual(self.s.require_int("server.port"), 8080)

    def test_require_int_from_string(self):
        s = ConfigStack()
        s.add_layer("d", {"n": "42", "neg": "-7"})
        self.assertEqual(s.require_int("n"), 42)
        self.assertEqual(s.require_int("neg"), -7)

    def test_require_int_bad_value_message(self):
        s = ConfigStack()
        s.add_layer("d", {"x": "abc", "f": 3.5, "b": True})
        with self.assertRaises(ValueError) as cm:
            s.require_int("x")
        self.assertEqual(str(cm.exception), "not an int: 'abc'")
        with self.assertRaises(ValueError) as cm:
            s.require_int("f")
        self.assertEqual(str(cm.exception), "not an int: 3.5")
        with self.assertRaises(ValueError) as cm:
            s.require_int("b")
        self.assertEqual(str(cm.exception), "not an int: True")

    def test_require_int_missing_message(self):
        with self.assertRaises(MissingKeyError) as cm:
            self.s.require_int("x.y")
        self.assertEqual(str(cm.exception), "required int not found: x.y")

    def test_require_section_found(self):
        sec = self.s.require_section("server")
        self.assertEqual(sec, {"host": "0.0.0.0", "port": 8080, "timeout": 30})

    def test_require_section_missing_message(self):
        with self.assertRaises(MissingKeyError) as cm:
            self.s.require_section("nope")
        self.assertEqual(str(cm.exception), "section 'nope' not found")

    def test_require_section_scalar_same_message(self):
        s = ConfigStack()
        s.add_layer("d", {"a": 5})
        with self.assertRaises(MissingKeyError) as cm:
            s.require_section("a")
        self.assertEqual(str(cm.exception), "section 'a' not found")

    def test_as_dict_copy_independent(self):
        d = self.s.as_dict()
        d["server"]["port"] = 1
        self.assertEqual(self.s.get("server.port"), 8080)

    def test_as_dict_value(self):
        self.assertEqual(
            self.s.as_dict(),
            {
                "server": {"host": "0.0.0.0", "port": 8080, "timeout": 30},
                "log": {"level": "info"},
                "features": {"beta": True},
            },
        )


class TestFilesAndLoadConfig(unittest.TestCase):
    def test_add_file_layer(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "gw.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"server": {"port": 8080}}, f)
            s = ConfigStack()
            s.add_layer("defaults", DEFAULTS)
            s.add_file("file", p)
            self.assertEqual(s.get("server.port"), 8080)
            self.assertEqual(s.get("server.host"), "0.0.0.0")

    def test_add_file_missing(self):
        s = ConfigStack()
        with self.assertRaises(FileNotFoundError):
            s.add_file("file", "/nonexistent/gsb-no-such.json")

    def test_add_file_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "broken.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{not json")
            s = ConfigStack()
            with self.assertRaises(ValueError):
                s.add_file("file", p)

    def test_add_file_non_dict_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "list.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("[1, 2]")
            s = ConfigStack()
            with self.assertRaises(TypeError) as cm:
                s.add_file("file", p)
            self.assertEqual(str(cm.exception), "layer file: expected dict, got list")

    def test_load_config_convenience(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "gw.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(FILE_LAYER, f)
            env = {"GW__server__timeout": "15", "GW__log__level": "debug"}
            with mock.patch.dict(os.environ, env):
                s = load_config(DEFAULTS, p, "GW")
            self.assertEqual(s.layers(), ["defaults", "file", "env"])
            self.assertEqual(s.get("server.port"), 8080)
            self.assertEqual(s.get("server.timeout"), "15")
            self.assertEqual(s.get("log.level"), "debug")
            self.assertEqual(s.get("server.host"), "0.0.0.0")
            self.assertIs(s.get("features.beta"), True)


if __name__ == "__main__":
    unittest.main()
