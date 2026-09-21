"""插件清单解析与版本工具。

插件的 PLUGIN 字典至少要给出 name 与 version：name 必须等于文件名主体，
version 形如 1.2.3；description 可选；requires 可选，是本插件依赖的
其他插件名列表，装载按依赖序 init。
"""

import re

from replug.errors import ManifestError

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def parse_version(text):
    """把 1.2.3 解析成 (1, 2, 3)，格式不对抛 ManifestError。"""
    if not isinstance(text, str) or not _VERSION_RE.match(text):
        raise ManifestError("版本号格式不对: %r" % (text,))
    return tuple(int(part) for part in text.split("."))


def compare_versions(left, right):
    """比较两个版本字符串：左小 -1，相等 0，左大 1。"""
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


class PluginManifest:
    """一次装载时冻结下来的插件身份。"""

    __slots__ = ("name", "version", "description", "requires")

    def __init__(self, name, version, description="", requires=()):
        self.name = name
        self.version = version
        self.description = description
        self.requires = tuple(requires)

    def __repr__(self):
        return "PluginManifest(name=%r, version=%r)" % (self.name, self.version)


def parse_manifest(raw, expected_name, path):
    """校验模块里的 PLUGIN 字典，name 必须等于文件名主体。"""
    if not isinstance(raw, dict):
        raise ManifestError("%s 的 PLUGIN 不是字典" % path)
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ManifestError("%s 的 PLUGIN 缺 name" % path)
    if name != expected_name:
        raise ManifestError("%s 的 name %r 与文件名 %r 对不上"
                            % (path, name, expected_name))
    parse_version(raw.get("version"))
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ManifestError("%s 的 description 不是字符串" % path)
    requires_raw = raw.get("requires", [])
    if not isinstance(requires_raw, (list, tuple)):
        raise ManifestError("%s 的 requires 不是列表" % path)
    requires = []
    for dep in requires_raw:
        if not isinstance(dep, str) or not dep:
            raise ManifestError("%s 的 requires 里有非法插件名" % path)
        requires.append(dep)
    if len(set(requires)) != len(requires):
        raise ManifestError("%s 的 requires 有重复依赖" % path)
    if name in requires:
        raise ManifestError("%s 的 requires 不能包含自己" % path)
    return PluginManifest(name, raw["version"], description, requires)
