"""构建清单的解析。

清单是行式文本，每行一个目标：

    目标名: 依赖1 依赖2

`#` 起始的注释与空行忽略；无依赖的目标冒号后留空。
声明顺序在解析后保留，分层与报告顺序都依赖这个顺序。
"""

from dataclasses import dataclass

from .errors import ManifestError


@dataclass(frozen=True)
class Target:
    """一个构建目标：名字 + 直接依赖（保持书写顺序）。"""

    name: str
    deps: tuple


class Manifest:
    """解析后的清单：目标集合 + 声明顺序。"""

    def __init__(self, targets):
        # targets: 按声明顺序的 Target 列表
        self.targets = {t.name: t for t in targets}
        self.order = [t.name for t in targets]

    def __contains__(self, name):
        return name in self.targets

    def __len__(self):
        return len(self.order)


def parse_manifest(text):
    """解析清单文本。语法错误、目标名非法或重复定义抛 ManifestError。"""
    targets = []
    seen = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ManifestError(f"第 {lineno} 行缺少冒号: {raw.strip()!r}")
        name, _, dep_part = line.partition(":")
        name = name.strip()
        deps = tuple(dep_part.split())
        if not name or " " in name:
            raise ManifestError(f"第 {lineno} 行目标名非法: {name!r}")
        if name in seen:
            raise ManifestError(f"第 {lineno} 行重复定义目标 {name!r}")
        seen.add(name)
        targets.append(Target(name, deps))
    if not targets:
        raise ManifestError("清单里没有任何目标")
    return Manifest(targets)
