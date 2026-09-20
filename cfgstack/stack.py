"""cfgstack: 配置分层合并。defaults < file < env，网关和三个后台任务的启动路径在用。

行为口径（历史形成的，全部要保住，tests/test_cfgstack.py 是清单）：
- 层合并是深合并：上层只覆盖自己给出的键，同节其他键保留
- env 变量名形如 PREFIX__section__key，多段路径用 __ 分隔，值一律当字符串
- 各 require_* 缺键时的报错文案是各自的历史措辞，逐字依赖，别统一
"""

import json
import os


class MissingKeyError(Exception):
    """配置缺键。渲染成什么文案由各调用点决定（历史措辞，tests 逐字锁着）。"""


def _merge_inplace(dst, src):
    """把 src 深合并进 dst，就地改。"""
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            _merge_inplace(dst[k], v)
        else:
            dst[k] = v


def _copy_tree(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _copy_tree(v)
        else:
            out[k] = v
    return out


def _walk_set(data, path, value):
    """按 dotted path 写入嵌套 dict，中间层缺就建。"""
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


class ConfigStack(object):
    """分层配置栈。层按调用先后叠加，后加的覆盖先加的。"""

    def __init__(self):
        self._data = {}
        self._layers = []

    def add_layer(self, name, data):
        if not isinstance(data, dict):
            raise TypeError(
                "layer %s: expected dict, got %s" % (name, type(data).__name__)
            )
        self._layers.append(name)
        for k, v in data.items():
            if isinstance(v, dict):
                v = _copy_tree(v)
            if k in self._data and isinstance(self._data[k], dict) and isinstance(v, dict):
                _merge_inplace(self._data[k], v)
            else:
                self._data[k] = v

    def add_file(self, name, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.add_layer(name, data)

    def apply_env(self, prefix):
        sep = prefix + "__"
        found = {}
        for env_name in sorted(os.environ):
            if not env_name.startswith(sep):
                continue
            rest = env_name[len(sep):]
            parts = rest.split("__")
            skip = False
            for p in parts:
                if p == "":
                    skip = True
            if skip:
                continue
            found[".".join(parts)] = os.environ[env_name]
        self._layers.append("env")
        for path in found:
            _walk_set(self._data, path, found[path])

    def layers(self):
        return list(self._layers)

    def as_dict(self):
        return _copy_tree(self._data)

    def _lookup(self, key):
        cur = self._data
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None, False
            cur = cur[part]
        return cur, True

    def get(self, key, default=None):
        v, ok = self._lookup(key)
        if not ok:
            return default
        return v

    def require(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise MissingKeyError("missing key: %s" % key)
        return v

    def require_int(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise MissingKeyError("required int not found: %s" % key)
        if isinstance(v, bool):
            raise ValueError("not an int: %r" % (v,))
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                pass
        raise ValueError("not an int: %r" % (v,))

    def require_section(self, name):
        v, ok = self._lookup(name)
        if not ok or not isinstance(v, dict):
            raise MissingKeyError("section '%s' not found" % name)
        return v


def merge_dicts(a, b):
    """深合并两个 dict，返回新 dict，入参不动。"""
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_dicts(out[k], v)
        else:
            out[k] = v
    return out


def merge_profiles(base, *overrides):
    """依次叠加多个 profile，后面的赢。"""
    out = base
    for ov in overrides:
        out = merge_dicts(out, ov)
    return out


def required_subset(mapping, keys, source):
    """从 mapping 里挑出必选键。缺键按 source 报错。"""
    out = {}
    for k in keys:
        if k not in mapping:
            raise MissingKeyError("key %r missing in %s" % (k, source))
        out[k] = mapping[k]
    return out


def load_config(defaults, file_path, env_prefix):
    """网关用的标准入口：defaults -> file -> env 依次叠加。"""
    stack = ConfigStack()
    stack.add_layer("defaults", defaults)
    stack.add_file("file", file_path)
    stack.apply_env(env_prefix)
    return stack
