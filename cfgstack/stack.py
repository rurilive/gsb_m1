"""cfgstack: 配置分层合并。defaults < file < env，网关和三个后台任务的启动路径在用。

行为口径（历史形成的，全部要保住，tests/test_cfgstack.py 是清单）：
- 层合并是深合并：上层只覆盖自己给出的键，同节其他键保留
- env 变量名形如 PREFIX__section__key，多段路径用 __ 分隔，值一律当字符串
- 各 require_* 缺键时的报错文案是各自的历史措辞，逐字依赖，别统一
"""

import json
import os


# 各访问点缺键时的历史文案（逐字依赖，tests 锁着）。
_MISSING_MESSAGES = {
    "require": "missing key: %(key)s",
    "require_int": "required int not found: %(key)s",
    "require_section": "section '%(key)s' not found",
}


class MissingKeyError(Exception):
    """结构化缺键错误：携带缺失的键与访问来源（来源审计用）。

    文案不在调用点手拼，统一由本类按 key/source/kind 渲染回历史原文。
    兼容旧式直接传 message 的构造。
    """

    def __init__(self, message=None, key=None, source=None, kind=None):
        if message is None and key is not None:
            message = _render_missing(key, source, kind)
        super(MissingKeyError, self).__init__(message)
        self.key = key
        self.source = source
        self.kind = kind


def _missing_key_error(key, source, kind):
    """所有缺键的唯一构造点：结构化字段进，历史文案出。"""
    return MissingKeyError(key=key, source=source, kind=kind)


def _render_missing(key, source, kind):
    """把结构化缺键信息渲染成该访问点的历史文案（逐字）。"""
    template = _MISSING_MESSAGES.get(kind)
    if template is not None:
        return template % {"key": key}
    return "key %r missing in %s" % (key, source)


def _merge_trees(dst, src):
    """唯一的深合并：把 src 叠到 dst 上，dict+dict 递归，其余 src 赢。

    src 里每个 dict 节点都会重建，故 _merge_trees({}, d) 即 d 的深拷贝，
    层入栈、env 落树、as_dict 导出全部走这一个函数（标量叶子共享无妨）。
    """
    out = dict(dst)
    for k, v in src.items():
        if isinstance(v, dict):
            base = out[k] if k in out and isinstance(out[k], dict) else {}
            out[k] = _merge_trees(base, v)
        else:
            out[k] = v
    return out


def _copy_tree(d):
    """深拷贝一棵配置树（dict 节点全新，标量/其他值保持原样）。"""
    return _merge_trees({}, d)


def _walk_set(data, path, value):
    """按 dotted path 写入嵌套 dict，中间层缺就建。"""
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


class _Layer(object):
    """管道中的一层：声明顺序就是优先级，列表越靠后赢。"""

    def __init__(self, name, tree):
        self.name = name
        self.tree = tree


class ConfigStack(object):
    """分层配置栈：层是一条显式管道，声明（add_*）顺序即优先级。"""

    def __init__(self):
        self._pipeline = []
        self._merged = {}

    def add_layer(self, name, data):
        if not isinstance(data, dict):
            raise TypeError(
                "layer %s: expected dict, got %s" % (name, type(data).__name__)
            )
        tree = _copy_tree(data)
        self._pipeline.append(_Layer(name, tree))
        self._merged = _merge_trees(self._merged, tree)

    def add_file(self, name, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.add_layer(name, data)

    def apply_env(self, prefix):
        sep = prefix + "__"
        env_tree = {}
        for env_name in sorted(os.environ):
            if not env_name.startswith(sep):
                continue
            rest = env_name[len(sep):]
            parts = rest.split("__")
            if any(p == "" for p in parts):
                continue
            _walk_set(env_tree, ".".join(parts), os.environ[env_name])
        self._pipeline.append(_Layer("env", env_tree))
        self._merged = _merge_trees(self._merged, env_tree)

    def layers(self):
        return [layer.name for layer in self._pipeline]

    def as_dict(self):
        return _copy_tree(self._merged)

    def _lookup(self, key):
        cur = self._merged
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
            raise _missing_key_error(key, "require", "require")
        return v

    def require_int(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise _missing_key_error(key, "require_int", "require_int")
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
            raise _missing_key_error(name, "require_section", "require_section")
        return v


def merge_dicts(a, b):
    """深合并两个 dict，返回新 dict，入参不动。"""
    return _merge_trees(a, b)


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
            raise _missing_key_error(k, source, "required_subset")
        out[k] = mapping[k]
    return out


def load_config(defaults, file_path, env_prefix):
    """网关用的标准入口：defaults -> file -> env 依次叠加。"""
    stack = ConfigStack()
    stack.add_layer("defaults", defaults)
    stack.add_file("file", file_path)
    stack.apply_env(env_prefix)
    return stack
