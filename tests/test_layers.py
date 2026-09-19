"""三层配置（默认 < JSON 文件 < CONFY_ 环境变量）的行为测试。"""

import json
import os
import tempfile
import unittest
from unittest import mock

from confy import (
    ConfigErrors,
    MissingKeyError,
    describe,
    export,
    get,
    load,
    missing,
    require,
    section,
    source_of,
    typed,
    validate,
)


def reset_layers():
    load(paths=[], environ={})


class LayerTestCase(unittest.TestCase):
    def setUp(self):
        reset_layers()

    def tearDown(self):
        reset_layers()

    def write_json(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        self.addCleanup(os.unlink, path)
        return path


class TestLoadPrecedence(LayerTestCase):
    def test_defaults_only_without_load(self):
        self.assertEqual(get("db.pool_size"), 8)
        self.assertEqual(source_of("db.pool_size"), "defaults")

    def test_file_overrides_defaults(self):
        path = self.write_json({"db": {"pool_size": 32}})
        load([path], {})
        self.assertEqual(get("db.pool_size"), 32)
        self.assertEqual(source_of("db.pool_size"), f"file:{path}")

    def test_env_overrides_file(self):
        path = self.write_json({"db": {"pool_size": 32}})
        load([path], {"CONFY_DB__POOL_SIZE": "64"})
        self.assertEqual(get("db.pool_size"), 64)
        self.assertEqual(source_of("db.pool_size"), "env:CONFY_DB__POOL_SIZE")

    def test_later_file_overrides_earlier(self):
        first = self.write_json({"db": {"pool_size": 32}})
        second = self.write_json({"db": {"pool_size": 48}})
        load([first, second], {})
        self.assertEqual(get("db.pool_size"), 48)
        self.assertEqual(source_of("db.pool_size"), f"file:{second}")

    def test_file_can_add_new_keys(self):
        path = self.write_json({"mail": {"smtp": {"password": "s3cret"}}})
        load([path], {})
        self.assertEqual(get("mail.smtp.password"), "s3cret")
        self.assertEqual(source_of("mail.smtp.password"), f"file:{path}")

    def test_env_can_add_new_keys(self):
        load([], {"CONFY_FEATURE__BETA": "true"})
        self.assertIs(get("feature.beta"), True)

    def test_environ_defaults_to_os_environ(self):
        with mock.patch.dict(os.environ, {"CONFY_X__Y": "9"}, clear=True):
            load()
        self.assertEqual(get("x.y"), 9)

    def test_load_returns_merged_view(self):
        view = load([], {"CONFY_DB__POOL_SIZE": "64"})
        self.assertEqual(view["db.pool_size"], 64)
        self.assertEqual(view["app.name"], "orders")


class TestEnvMapping(LayerTestCase):
    def test_only_confy_prefix_counts(self):
        load([], {"OTHER_DB__POOL_SIZE": "99", "DB__POOL_SIZE": "98"})
        self.assertEqual(get("db.pool_size"), 8)

    def test_double_underscore_maps_to_dot(self):
        load([], {"CONFY_DB__POOL_SIZE": "16"})
        self.assertEqual(get("db.pool_size"), 16)

    def test_single_underscore_stays_in_segment(self):
        load([], {"CONFY_CACHE__TTL_SECONDS": "5"})
        self.assertEqual(get("cache.ttl_seconds"), 5)

    def test_names_are_case_insensitive_to_lowercase_keys(self):
        load([], {"CONFY_LOG__LEVEL": "debug"})
        self.assertEqual(get("log.level"), "debug")


class TestEnvTypeInference(LayerTestCase):
    def infer(self, text):
        load([], {"CONFY_PROBE__VALUE": text})
        return get("probe.value")

    def test_true_false_become_bool(self):
        self.assertIs(self.infer("true"), True)
        self.assertIs(self.infer("false"), False)

    def test_pure_integer_becomes_int(self):
        value = self.infer("42")
        self.assertEqual(value, 42)
        self.assertIs(type(value), int)
        self.assertEqual(self.infer("-7"), -7)

    def test_decimal_or_exponent_becomes_float(self):
        self.assertEqual(self.infer("3.5"), 3.5)
        self.assertEqual(self.infer("1e3"), 1000.0)
        self.assertIs(type(self.infer("1e3")), float)

    def test_everything_else_stays_string(self):
        self.assertEqual(self.infer("info"), "info")
        self.assertEqual(self.infer("1.2.3"), "1.2.3")
        self.assertEqual(self.infer("12px"), "12px")


class TestJsonNativeTypes(LayerTestCase):
    def test_json_types_preserved(self):
        path = self.write_json(
            {
                "app": {"debug": True},
                "db": {"options": {"ssl": True, "timeout": 1.5}},
                "worker": {"queues": ["a", "b"]},
                "http": {"request_timeout": 0.25},
            }
        )
        load([path], {})
        self.assertIs(get("app.debug"), True)
        self.assertEqual(get("db.options"), {"ssl": True, "timeout": 1.5})
        self.assertEqual(get("worker.queues"), ["a", "b"])
        self.assertIs(type(get("http.request_timeout")), float)


class TestMergedViewApi(LayerTestCase):
    def test_old_entrypoints_read_merged_view(self):
        path = self.write_json({"db": {"pool_size": 32}})
        load([path], {"CONFY_LOG__LEVEL": "debug"})
        self.assertEqual(require("db.pool_size"), 32)
        self.assertEqual(section("db")["pool_size"], 32)
        self.assertEqual(export()["log.level"], "debug")
        self.assertIn("log.level = 'debug' (str)", describe())
        self.assertEqual(missing(["log.level", "nope.key"]), ["nope.key"])

    def test_defaults_untouched_by_overrides(self):
        from confy import CONFIG

        load([], {"CONFY_DB__POOL_SIZE": "64"})
        self.assertEqual(CONFIG["db.pool_size"], 8)


class TestTyped(LayerTestCase):
    def test_returns_value_when_type_matches(self):
        self.assertEqual(typed("db.port", int), 5432)
        self.assertIs(typed("app.debug", bool), False)
        self.assertEqual(typed("worker.queues", list), ["default", "mail"])

    def test_missing_raises_keyerror(self):
        with self.assertRaises(KeyError):
            typed("nope.key", int)
        with self.assertRaises(MissingKeyError):
            typed("nope.key", int)

    def test_mismatch_raises_typeerror(self):
        with self.assertRaises(TypeError):
            typed("app.name", int)

    def test_bool_is_not_int(self):
        with self.assertRaises(TypeError):
            typed("app.debug", int)

    def test_int_is_not_bool(self):
        with self.assertRaises(TypeError):
            typed("db.port", bool)

    def test_env_inference_feeds_typed(self):
        load([], {"CONFY_DB__POOL_SIZE": "64"})
        self.assertEqual(typed("db.pool_size", int), 64)


class TestValidate(LayerTestCase):
    def test_valid_schema_passes(self):
        validate({"db.port": int, "app.name": str, "app.debug": bool})

    def test_missing_and_mismatch_aggregated(self):
        load([], {"CONFY_DB__PORT": "not-an-int"})
        with self.assertRaises(ConfigErrors) as ctx:
            validate({"db.port": int, "nope.key": str, "app.name": str})
        errors = {e.key: e for e in ctx.exception.errors}
        self.assertEqual(set(errors), {"db.port", "nope.key"})

    def test_error_carries_key_reason_layer(self):
        load([], {"CONFY_DB__PORT": "not-an-int"})
        with self.assertRaises(ConfigErrors) as ctx:
            validate({"db.port": int, "nope.key": str})
        errors = {e.key: e for e in ctx.exception.errors}
        self.assertEqual(errors["db.port"].reason, "expected int, got str")
        self.assertEqual(errors["db.port"].layer, "env:CONFY_DB__PORT")
        self.assertEqual(errors["nope.key"].reason, "missing")
        self.assertIsNone(errors["nope.key"].layer)

    def test_file_layer_reported(self):
        path = self.write_json({"db": {"port": "not-an-int"}})
        load([path], {})
        with self.assertRaises(ConfigErrors) as ctx:
            validate({"db.port": int})
        self.assertEqual(ctx.exception.errors[0].layer, f"file:{path}")

    def test_bool_not_int_in_validate(self):
        with self.assertRaises(ConfigErrors):
            validate({"app.debug": int})


class TestSourceOf(LayerTestCase):
    def test_three_layers(self):
        path = self.write_json({"db": {"pool_size": 32}})
        load([path], {"CONFY_LOG__LEVEL": "debug"})
        self.assertEqual(source_of("app.name"), "defaults")
        self.assertEqual(source_of("db.pool_size"), f"file:{path}")
        self.assertEqual(source_of("log.level"), "env:CONFY_LOG__LEVEL")

    def test_missing_key_raises(self):
        with self.assertRaises(MissingKeyError):
            source_of("nope.key")


if __name__ == "__main__":
    unittest.main()
