"""confy 的读取入口：get / require / section / describe。

当前只读 store.CONFIG 这一份内置 dict，没有任何装载动作，
值在 import 时就定死了。
"""

from confy.errors import MissingKeyError
from confy.store import CONFIG, is_branch, leaf_keys

__all__ = [
    "MissingKeyError",
    "describe",
    "export",
    "get",
    "missing",
    "require",
    "section",
]


def get(key, default=None):
    """读取叶子值；缺失时返回 default，分支键视同缺失。"""
    if key in CONFIG:
        return CONFIG[key]
    return default


def require(key):
    """读取必配叶子值；缺失抛 MissingKeyError。"""
    if key not in CONFIG:
        raise MissingKeyError(key)
    return CONFIG[key]


def section(prefix):
    """取分支键下的整棵子树，返回去掉前缀的 dict 副本。

    叶子键或未知键抛 MissingKeyError。
    """
    if not is_branch(prefix):
        raise MissingKeyError(prefix)
    stem = prefix + "."
    out = {}
    for k, v in CONFIG.items():
        if k.startswith(stem):
            out[k[len(stem):]] = v
    return out


def export():
    """全部叶子键到值的浅拷贝字典。"""
    return {k: v for k, v in CONFIG.items() if not is_branch(k)}


def missing(required_keys):
    """启动检查助手：返回 required_keys 里缺失的键列表。"""
    return [k for k in required_keys if k not in CONFIG]


def describe():
    """人类可读的配置清单：每行 "key = value (type)"。"""
    lines = []
    for key in leaf_keys():
        value = CONFIG[key]
        lines.append(f"{key} = {value!r} ({type(value).__name__})")
    return lines
