"""confy 的读取入口：get / require / section / typed / validate 等。

全部读 load() 维护的三层合并视图（默认 < JSON 文件 < CONFY_ 环境变量），
未调用 load() 时等同于只读 store.CONFIG 内置默认层。
"""

from confy.errors import ConfigError, ConfigErrors, MissingKeyError
from confy.layers import is_branch, leaf_keys, load, merged, source_of

__all__ = [
    "ConfigError",
    "ConfigErrors",
    "MissingKeyError",
    "describe",
    "export",
    "get",
    "load",
    "missing",
    "require",
    "section",
    "source_of",
    "typed",
    "validate",
]


def get(key, default=None):
    """读取叶子值；缺失时返回 default，分支键视同缺失。"""
    view = merged()
    if key in view:
        return view[key]
    return default


def require(key):
    """读取必配叶子值；缺失抛 MissingKeyError。"""
    view = merged()
    if key not in view:
        raise MissingKeyError(key)
    return view[key]


def section(prefix):
    """取分支键下的整棵子树，返回去掉前缀的 dict 副本。

    叶子键或未知键抛 MissingKeyError。
    """
    if not is_branch(prefix):
        raise MissingKeyError(prefix)
    stem = prefix + "."
    out = {}
    for k, v in merged().items():
        if k.startswith(stem):
            out[k[len(stem):]] = v
    return out


def export():
    """全部叶子键到值的浅拷贝字典。"""
    return {k: v for k, v in merged().items() if not is_branch(k)}


def missing(required_keys):
    """启动检查助手：返回 required_keys 里缺失的键列表。"""
    view = merged()
    return [k for k in required_keys if k not in view]


def describe():
    """人类可读的配置清单：每行 "key = value (type)"。"""
    view = merged()
    lines = []
    for key in leaf_keys():
        value = view[key]
        lines.append(f"{key} = {value!r} ({type(value).__name__})")
    return lines


def _matches_type(value, expected):
    if isinstance(expected, tuple):
        return any(_matches_type(value, t) for t in expected)
    if expected is bool:
        return isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def _type_name(expected):
    if isinstance(expected, tuple):
        return " | ".join(t.__name__ for t in expected)
    return expected.__name__


def typed(key, expected):
    """按类型读取叶子值。

    缺失抛 MissingKeyError；类型不符抛 TypeError（bool 不算 int）。
    """
    view = merged()
    if key not in view:
        raise MissingKeyError(key)
    value = view[key]
    if not _matches_type(value, expected):
        raise TypeError(
            f"{key}: 期望 {_type_name(expected)}，实际 "
            f"{type(value).__name__}（来源 {source_of(key)}）"
        )
    return value


def validate(schema):
    """按 {key: type} 校验合并视图。

    缺失与类型不符聚成 ConfigErrors 一次抛出（每项带 key/原因/层）；
    全部通过返回 None。
    """
    view = merged()
    errors = []
    for key, expected in schema.items():
        if key not in view:
            errors.append(ConfigError(key, "缺失", None))
            continue
        value = view[key]
        if not _matches_type(value, expected):
            reason = f"期望 {_type_name(expected)}，实际 {type(value).__name__}"
            errors.append(ConfigError(key, reason, source_of(key)))
    if errors:
        raise ConfigErrors(errors)
