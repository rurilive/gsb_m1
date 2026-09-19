"""三层配置的装载与合并：内置默认 < JSON 文件 < CONFY_ 环境变量。

load() 重建层栈，老接口（get/require/section/...）统一读合并视图。
"""

import json
import os
import re

from confy.store import CONFIG as DEFAULTS

ENV_PREFIX = "CONFY_"

_INT_RE = re.compile(r"[+-]?\d+")
_FLOAT_RE = re.compile(
    r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|[+-]?\d+[eE][+-]?\d+"
)

__all__ = [
    "ENV_PREFIX",
    "child_keys",
    "infer_env_value",
    "is_branch",
    "key_to_var",
    "leaf_keys",
    "load",
    "merged",
    "source_of",
    "var_to_key",
]


def infer_env_value(raw):
    """环境变量字符串推断：true/false->bool、纯整数->int、小数或e->float、其余字符串。"""
    if not isinstance(raw, str):
        return raw
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if _INT_RE.fullmatch(raw):
        return int(raw)
    if _FLOAT_RE.fullmatch(raw):
        return float(raw)
    return raw


def var_to_key(var_name):
    """CONFY_DB__POOL_SIZE -> db.pool_size；非 CONFY_ 前缀返回 None。"""
    if not var_name.startswith(ENV_PREFIX):
        return None
    rest = var_name[len(ENV_PREFIX):]
    if not rest:
        return None
    return ".".join(part.lower() for part in rest.split("__"))


def key_to_var(key):
    """db.pool_size -> CONFY_DB__POOL_SIZE。"""
    return ENV_PREFIX + key.upper().replace(".", "__")


class _Layer:
    """一层配置：kind 为 defaults / file / env，values 为扁平点号键 dict。"""

    def __init__(self, kind, label=None):
        self.kind = kind
        self.label = label
        self.values = {}
        self.varnames = {}  # 仅 env 层：key -> 原始变量名

    def source(self, key):
        if self.kind == "env":
            return f"env:{self.varnames.get(key, key_to_var(key))}"
        if self.kind == "file":
            return f"file:{self.label}"
        return "defaults"


_layers = []
_merged = None


def _reset():
    global _layers, _merged
    base = _Layer("defaults")
    base.values = DEFAULTS
    _layers = [base]
    _merged = None


_reset()


def load(paths=None, environ=None):
    """重建配置层：内置默认 < JSON 文件（后者覆盖前者） < CONFY_ 环境变量。

    paths 为扁平 JSON 文件（点号键 -> 任意 JSON 原生值）；environ 缺省取
    os.environ，可注入 dict 便于测试。重复调用会丢弃之前的文件/环境层。
    """
    global _merged
    if environ is None:
        environ = os.environ
    _reset()
    for path in paths or []:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"配置文件必须是扁平 JSON 对象: {path}")
        layer = _Layer("file", label=str(path))
        layer.values = dict(data)
        _layers.append(layer)
    env_layer = _Layer("env")
    for name, raw in environ.items():
        key = var_to_key(name)
        if key is None:
            continue
        env_layer.values[key] = infer_env_value(raw)
        env_layer.varnames[key] = name
    if env_layer.values:
        _layers.append(env_layer)
    _merged = None


def merged():
    """三层合并后的扁平视图（高层覆盖低层），带缓存。"""
    global _merged
    if _merged is None:
        view = {}
        for layer in _layers:
            view.update(layer.values)
        _merged = view
    return _merged


def source_of(key):
    """key 的生效来源：defaults / file:路径 / env:变量名；未知键返回 None。"""
    for layer in reversed(_layers):
        if key in layer.values:
            return layer.source(key)
    return None


def is_branch(key):
    """key 是否是合并视图中其它键的分支前缀。"""
    prefix = key + "."
    return any(k.startswith(prefix) for k in merged())


def leaf_keys():
    """合并视图的全部叶子键。"""
    return [k for k in merged() if not is_branch(k)]


def child_keys(prefix):
    """prefix 分支下的直接子键名（不带前缀），按序去重。"""
    stem = prefix + "."
    seen = []
    for k in merged():
        if k.startswith(stem):
            child = k[len(stem):].split(".")[0]
            if child not in seen:
                seen.append(child)
    return seen
