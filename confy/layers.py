"""三层配置：内置默认 < JSON 文件 < CONFY_ 环境变量。

load() 重建配置层；api 的读取入口一律走 merged() 合并视图。
"""

import json
import os
import re

from confy.errors import ConfigError, ConfigErrors, MissingKeyError
from confy.store import CONFIG

ENV_PREFIX = "CONFY_"

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_MARKERS = (".", "e", "E")

_files = []  # [(路径, {点号键: 值})]，靠后的文件覆盖靠前的
_env = {}    # {点号键: (推断后的值, 原始变量名)}


def _infer(text):
    """环境变量字符串的类型推断。"""
    if text == "true":
        return True
    if text == "false":
        return False
    if _INT_RE.match(text):
        return int(text)
    if any(m in text for m in _FLOAT_MARKERS):
        try:
            return float(text)
        except ValueError:
            pass
    return text


def _leaf_keys_of(flat):
    return {k for k in flat if not any(o.startswith(k + ".") for o in flat)}


def _flatten(prefix, node, out, lower_leaves):
    # 嵌套 dict 展平成点号键；但若该路径在低层已是叶子（如 db.options），
    # 或遇到空 dict，则把整棵 dict 当作叶子值整体替换。
    if isinstance(node, dict) and node and prefix not in lower_leaves:
        for k, v in node.items():
            key = f"{prefix}.{k}" if prefix else k
            _flatten(key, v, out, lower_leaves)
    else:
        out[prefix] = node


def _env_key(var_name):
    body = var_name[len(ENV_PREFIX):]
    return ".".join(part.lower() for part in body.split("__"))


def _apply(view, flat):
    """把一层扁平键值合并进 view，清理叶子/分支互相覆盖的冲突键。"""
    for key in flat:
        for old in list(view):
            if old != key and (
                old.startswith(key + ".") or key.startswith(old + ".")
            ):
                del view[old]
    view.update(flat)


def load(paths=None, environ=None):
    """重置并重建配置层，返回合并视图。

    paths: JSON 文件路径列表（None 表示不读文件），靠后的覆盖靠前的；
    文件内嵌套对象展平成点号键，值保留 JSON 原生类型。
    environ: 环境变量映射，None 时取 os.environ；只认 CONFY_ 前缀，
    双下划线分层（db.pool_size 对应 CONFY_DB__POOL_SIZE）。
    """
    _files.clear()
    _env.clear()
    view = dict(CONFIG)
    for path in paths or []:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        flat = {}
        _flatten("", data, flat, _leaf_keys_of(view))
        _files.append((path, flat))
        _apply(view, flat)
    if environ is None:
        environ = os.environ
    for name, text in environ.items():
        if name.startswith(ENV_PREFIX):
            _env[_env_key(name)] = (_infer(text), name)
    return merged()


def merged():
    """defaults < JSON 文件 < 环境变量 的合并视图（新 dict）。"""
    view = dict(CONFIG)
    for _, flat in _files:
        _apply(view, flat)
    _apply(view, {k: v for k, (v, _) in _env.items()})
    return view


def is_branch(key):
    """key 是否是合并视图中其它键的分支前缀。"""
    prefix = key + "."
    return any(k.startswith(prefix) for k in merged())


def leaf_keys():
    """合并视图的全部叶子键，按定义顺序。"""
    view = merged()
    return [k for k in view if not is_branch(k)]


def child_keys(prefix):
    """合并视图中 prefix 分支下的直接子键名（不带前缀），按定义顺序去重。"""
    stem = prefix + "."
    seen = []
    for k in merged():
        if k.startswith(stem):
            child = k[len(stem):].split(".")[0]
            if child not in seen:
                seen.append(child)
    return seen


def source_of(key):
    """key 当前取值的来源层：defaults / file:路径 / env:变量名。"""
    if key in _env:
        return f"env:{_env[key][1]}"
    for path, flat in reversed(_files):
        if key in flat:
            return f"file:{path}"
    if key in CONFIG:
        return "defaults"
    raise MissingKeyError(key)


def _matches(value, typ):
    if typ is bool:
        return isinstance(value, bool)
    if typ is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, typ)


def typed(key, typ):
    """按类型严格读取；缺失抛 MissingKeyError，类型不符抛 TypeError。

    bool 不算 int（Python 里 bool 是 int 子类，这里显式排除）。
    """
    view = merged()
    if key not in view:
        raise MissingKeyError(key)
    value = view[key]
    if not _matches(value, typ):
        raise TypeError(
            f"{key}: 期望 {typ.__name__}，实际 {type(value).__name__}（{value!r}）"
        )
    return value


def validate(schema):
    """按 {key: type} 校验合并视图；缺失与类型不符聚成 ConfigErrors 一次抛出。"""
    view = merged()
    errors = []
    for key, typ in schema.items():
        if key not in view:
            errors.append(ConfigError(key, "missing", None))
        elif not _matches(view[key], typ):
            reason = f"expected {typ.__name__}, got {type(view[key]).__name__}"
            errors.append(ConfigError(key, reason, source_of(key)))
    if errors:
        raise ConfigErrors(errors)
