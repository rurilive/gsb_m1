"""replug: 本地插件运行时，纯标准库。

从插件目录装载 py 插件模块，调插件的 init 建实例状态，宿主按名字把请求
派给插件的 handle。支持一次性装载与不重启的 reload 热重载。
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
