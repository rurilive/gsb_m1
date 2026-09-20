"""cfgstack: 配置分层合并。defaults < file < env，网关和三个后台任务的启动路径在用。

行为口径（历史形成的，全部要保住，tests/test_cfgstack.py 是清单）：
- 层合并是深合并：上层只覆盖自己给出的键，同节其他键保留
- env 变量名形如 PREFIX__section__key，多段路径用 __ 分隔，值一律当字符串
- 各 require_* 缺键时的报错文案是各自的历史措辞，逐字依赖，别统一

结构：层是显式管道（ConfigStack._layers，声明顺序即优先级，低 -> 高），
合并只在 merge_dicts 一处实现，管道折叠、add_layer、apply_env 都走它。
"""

import json
import os


# 各调用点的历史缺键文案：只准在这里集中渲染，逐字被 tests 锁着，别统一措辞。
_MISSING_KEY_MESSAGES = {
    "require": "missing key: {key}",
    "require_int": "required int not found: {key}",
    "require_section": "section {key!r} not found",
    "required_subset": "key {key!r} missing in {source}",
}


class MissingKeyError(Exception):
    """结构化缺键错误：携带 kind/key/source，文案按 kind 集中渲染回历史原文。

    kind 标明触发点（require / require_int / require_section / required_subset），
    key 是缺失的键，source 是查找来源（栈上找过的层名元组，或调用方给的来源名）。
    仍兼容旧用法 MissingKeyError("整句文案")。
    """

    def __init__(self, message=None, *, kind=None, key=None, source=None):
        self.kind = kind
        self.key = key
        self.source = source
        if message is None:
            message = _MISSING_KEY_MESSAGES[kind].format(key=key, source=source)
        super().__init__(message)

    @classmethod
    def _from_layers(cls, kind, key, layer_names):
        """栈上查找缺键：source 记录在哪些层里找过（为配置来源审计铺路）。"""
        return cls(kind=kind, key=key, source=tuple(layer_names))


def _copy_tree(value):
    """深拷贝一棵配置树：dict 递归复制，叶子（含 list 等）原样保留。"""
    if not isinstance(value, dict):
        return value
    return {k: _copy_tree(v) for k, v in value.items()}


def merge_dicts(a, b):
    """深合并两个 dict，返回新 dict，入参不动。整个包唯一的合并实现。

    同键且两边都是 dict 时递归合并；否则 b 的值整体覆盖 a
    （标量盖 dict、dict 盖标量同理）。
    """
    out = {k: _copy_tree(v) for k, v in a.items()}
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge_dicts(out[k], v)
        else:
            out[k] = _copy_tree(v)
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
            raise MissingKeyError(kind="required_subset", key=k, source=source)
        out[k] = mapping[k]
    return out


def _read_env_layer(prefix):
    """读 PREFIX__section__key 风格环境变量，返回本层贡献的嵌套 dict。

    值一律保留字符串；空路径段（裸前缀、尾随 __）忽略；环境遍历排序固定。
    这里只负责收集成本层数据，覆盖/合并统一交给 merge_dicts。
    """
    sep = prefix + "__"
    layer = {}
    for env_name in sorted(os.environ):
        if not env_name.startswith(sep):
            continue
        parts = env_name[len(sep):].split("__")
        if any(part == "" for part in parts):
            continue
        cur = layer
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = os.environ[env_name]
    return layer


class _Layer(object):
    """管道中的一层：名字 + 入栈时刻的配置快照（与外部数据隔离）。"""

    __slots__ = ("name", "data")

    def __init__(self, name, data):
        self.name = name
        self.data = _copy_tree(data)


class ConfigStack(object):
    """分层配置栈：显式管道，层按声明顺序从低到高排列，后加的覆盖先加的。"""

    def __init__(self):
        self._layers = []

    def add_layer(self, name, data):
        if not isinstance(data, dict):
            raise TypeError(
                "layer %s: expected dict, got %s" % (name, type(data).__name__)
            )
        self._layers.append(_Layer(name, data))

    def add_file(self, name, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.add_layer(name, data)

    def apply_env(self, prefix):
        self._layers.append(_Layer("env", _read_env_layer(prefix)))

    def layers(self):
        return [layer.name for layer in self._layers]

    def _merged(self):
        """沿管道从低优先级到高优先级折叠，每一步都走 merge_dicts。"""
        merged = {}
        for layer in self._layers:
            merged = merge_dicts(merged, layer.data)
        return merged

    def as_dict(self):
        return self._merged()

    def _lookup(self, key):
        cur = self._merged()
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
            raise MissingKeyError._from_layers("require", key, self.layers())
        return v

    def require_int(self, key):
        v, ok = self._lookup(key)
        if not ok:
            raise MissingKeyError._from_layers("require_int", key, self.layers())
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
            raise MissingKeyError._from_layers("require_section", name, self.layers())
        return v


def load_config(defaults, file_path, env_prefix):
    """网关用的标准入口：defaults -> file -> env 依次叠加。"""
    stack = ConfigStack()
    stack.add_layer("defaults", defaults)
    stack.add_file("file", file_path)
    stack.apply_env(env_prefix)
    return stack
