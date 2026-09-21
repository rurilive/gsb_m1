"""depsolve: 清单驱动的依赖解析（闭包收集 + 版本择优 + 拓扑序输出）。"""

from .resolver import (
    CircularDependencyError,
    ConflictError,
    ResolveError,
    Resolver,
    UnknownPackageError,
)

__all__ = [
    "Resolver",
    "ResolveError",
    "CircularDependencyError",
    "ConflictError",
    "UnknownPackageError",
    "resolve",
]


def resolve(manifest, requests, enabled=None):
    """解析 requests 的完整依赖闭包。

    返回拓扑序（被依赖者在前）的 "name@version" 列表；
    enabled 是显式启用的可选依赖名集合。
    """
    return Resolver(manifest, enabled=enabled).resolve(requests)
