"""三层配置的测试：load 合并、环境变量推断、typed/validate/source_of。"""

import json
import os
import tempfile
import unittest
from unittest import mock

from confy import (
    ConfigErrors,
    MissingKeyError,
    get,
    load,
    require,
    section,
    source_of,
    typed,
    validate,
)


class LayerTestCase(unittest.TestCase):
    def setUp(self):
        # 每个用例结束后复位为纯默认层，保护 test_settings 行为基线
        self.addCleanup(load, [], {})

    def write_json(self, data):
        fh = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        self.addCleanup(os.unlink, fh.name)
        json.dump(data, fh)
        fh.close()
        return fh.name


class TestLoadPrecedence(LayerTestCase):
    def test_defaults_only_without_load(self):
        self.assertEqual(get("db.pool_size"), 8)
        self.assertEqual(source_of("db.pool_size"), "defaults")

    def test_file_overrides_defaults(self):
        path = self.write_json({"db.pool_size": 16, "log.level": "debug"})
        load([path], {})
        self.assertEqual(get("db.pool_size"), 16)
        self.assertEqual(get("log.level"), "debug")
        self.assertEqual(source_of("db.pool_size"), f"file:{path}")
        # 未覆盖的键仍来自默认层
        self.assertEqual(get("db.port"), 5432)
        self.assertEqual(source_of("db.port"), "defaults")

    def test_later_file_overrides_earlier(self):
        first = self.write_json({"log.level": "debug"})
        second = self.write_json({"log.level": "warning"})
        load([first, second], {})
        self.assertEqual(get("log.level"), "warning")
        self.assertEqual(source_of("log.level"), f"file:{second}")

    def test_env_overrides_file(self):
        path = self.write_json({"db.pool_size": 16})
        load([path], {"CONFY_DB__POOL_SIZE": "32"})
        self.assertEqual(get("db.pool_size"), 32)
        self.assertEqual(source_of("db.pool_size"), "env:CONFY_DB__POOL_SIZE")

    def test_load_resets_previous_layers(self):
        path = self.write_json({"db.pool_size": 16})
        load([path], {"CONFY_LOG__LEVEL": "debug"})
        load([], {})
        self.assertEqual(get("db.pool_size"), 8)
        self.assertEqual(get("log.level"), "info")
        self.assertEqual(source_of("db.pool_size"), "defaults")

    def test_old_api_reads_merged_view(self):
        path = self.write_json({"db.pool_size": 16})
        load([path], {"CONFY_WORKER__CONCURRENCY": "12"})
        self.assertEqual(require("db.pool_size"), 16)
        self.assertEqual(section("db")["pool_size"], 16)
        self.assertEqual(section("worker")["concurrency"], 12)


class TestEnvLayer(LayerTestCase):
    def test_only_confy_prefix_counts(self):
        load([], {
            "DB__POOL_SIZE": "1",
            "CONFYD_DB__POOL_SIZE": "2",
            "OTHER": "x",
        })
        self.assertEqual(get("db.pool_size"), 8)

    def test_double_underscore_maps_to_dot(self):
        load([], {"CONFY_DB__POOL_SIZE": "24", "CONFY_NEW__POOL_SIZE": "3"})
        self.assertEqual(get("db.pool_size"), 24)
        self.assertEqual(get("new.pool_size"), 3)  # 单下划线留在段内

    def test_value_inference(self):
        load([], {
            "CONFY_T__BOOL_TRUE": "true",
            "CONFY_T__BOOL_FALSE": "false",
            "CONFY_T__INT": "42",
            "CONFY_T__NEG_INT": "-7",
            "CONFY_T__FLOAT": "3.5",
            "CONFY_T__SCI": "1e3",
            "CONFY_T__STR": "hello",
            "CONFY_T__STR_NUMISH": "12px",
        })
        self.assertIs(get("t.bool_true"), True)
        self.assertIs(get("t.bool_false"), False)
        self.assertEqual(get("t.int"), 42)
        self.assertEqual(get("t.neg_int"), -7)
        self.assertEqual(get("t.float"), 3.5)
        self.assertIsInstance(get("t.sci"), float)
        self.assertEqual(get("t.sci"), 1000.0)
        self.assertEqual(get("t.str"), "hello")
        self.assertEqual(get("t.str_numish"), "12px")

    def test_environ_defaults_to_os_environ(self):
        with mock.patch.dict(os.environ, {"CONFY_DB__POOL_SIZE": "64"}):
            load([])
            self.assertEqual(get("db.pool_size"), 64)
            self.assertEqual(source_of("db.pool_size"), "env:CONFY_DB__POOL_SIZE")

    def test_json_native_types_preserved(self):
        path = self.write_json({
            "extra.flag": True,
            "extra.limits": [1, 2],
            "extra.opts": {"a": 1},
            "extra.ratio": 0.5,
            "extra.none": None,
        })
        load([path], {})
        self.assertIs(get("extra.flag"), True)
        self.assertEqual(get("extra.limits"), [1, 2])
        self.assertEqual(get("extra.opts"), {"a": 1})
        self.assertIsInstance(get("extra.ratio"), float)
        self.assertIsNone(get("extra.none"))


class TestTyped(LayerTestCase):
    def test_returns_value_when_type_matches(self):
        self.assertEqual(typed("db.port", int), 5432)
        self.assertIs(typed("app.debug", bool), False)

    def test_missing_raises_keyerror(self):
        with self.assertRaises(MissingKeyError):
            typed("nope.key", str)

    def test_type_mismatch_raises_typeerror(self):
        with self.assertRaises(TypeError):
            typed("db.host", int)

    def test_bool_is_not_int(self):
        with self.assertRaises(TypeError):
            typed("app.debug", int)
        with self.assertRaises(TypeError):
            typed("db.port", bool)


class TestValidate(LayerTestCase):
    def test_ok_returns_none(self):
        self.assertIsNone(validate({"db.port": int, "app.name": str}))

    def test_aggregates_missing_and_mismatch(self):
        load([], {"CONFY_DB__POOL_SIZE": "16"})
        with self.assertRaises(ConfigErrors) as ctx:
            validate({
                "db.pool_size": str,       # 类型不符，env 层
                "log.level": str,          # 通过
                "mail.smtp.password": str, # 缺失
            })
        errors = list(ctx.exception)
        self.assertEqual(len(errors), 2)
        by_key = {e.key: e for e in errors}
        self.assertEqual(by_key["db.pool_size"].layer, "env:CONFY_DB__POOL_SIZE")
        self.assertIn("str", by_key["db.pool_size"].reason)
        self.assertIsNone(by_key["mail.smtp.password"].layer)
        self.assertIn("缺失", by_key["mail.smtp.password"].reason)

    def test_mismatch_layer_reports_file(self):
        path = self.write_json({"log.level": "debug"})
        load([path], {})
        with self.assertRaises(ConfigErrors) as ctx:
            validate({"log.level": int})
        (error,) = list(ctx.exception)
        self.assertEqual(error.layer, f"file:{path}")

    def test_bool_not_int_in_validate(self):
        with self.assertRaises(ConfigErrors):
            validate({"app.debug": int})


class TestSourceOf(LayerTestCase):
    def test_three_layers(self):
        path = self.write_json({"log.level": "debug"})
        load([path], {"CONFY_DB__POOL_SIZE": "16"})
        self.assertEqual(source_of("app.name"), "defaults")
        self.assertEqual(source_of("log.level"), f"file:{path}")
        self.assertEqual(source_of("db.pool_size"), "env:CONFY_DB__POOL_SIZE")

    def test_unknown_key_returns_none(self):
        self.assertIsNone(source_of("nope.key"))


if __name__ == "__main__":
    unittest.main()
