"""replug: 本地插件运行时，纯标准库。

从插件目录装载 py 插件模块，按 requires 依赖序调 init 建实例状态，宿主
按名字把请求派给插件的 handle；支持 load_all 全量装载与 reload 热重载。
"""

from replug.errors import (InitError, LoadError, ManifestError, MigrateError,
                           PluginError, PluginNotFound, ReplugError)
from replug.manifest import PluginManifest, compare_versions, parse_version
from replug.runtime import PluginContext, PluginRuntime

__all__ = [
    "InitError",
    "LoadError",
    "ManifestError",
    "MigrateError",
    "PluginContext",
    "PluginError",
    "PluginManifest",
    "PluginNotFound",
    "PluginRuntime",
    "ReplugError",
    "compare_versions",
    "parse_version",
]
