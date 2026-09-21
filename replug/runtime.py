"""插件宿主：从目录装载插件，把请求派发给插件处理。

一次性装载：load_all 把插件目录里所有 py 文件读进来，校验清单、调 init
建状态，装完就位。要么全部成功，要么一点不动地维持原样并抛错。
"""

import os

from replug.errors import (InitError, ManifestError, PluginError,
                           PluginNotFound, ReplugError)
from replug.loader import load_module
from replug.manifest import parse_manifest


class PluginContext:
    """init 拿到的上下文：这一个插件这次装载的身份。"""

    __slots__ = ("name", "version", "plugin_dir", "path")

    def __init__(self, name, version, plugin_dir, path):
        self.name = name
        self.version = version
        self.plugin_dir = plugin_dir
        self.path = path

    def __repr__(self):
        return "PluginContext(name=%r, version=%r)" % (self.name, self.version)


class _Plugin:
    """宿主里的一份插件实例：清单、模块与活状态。"""

    __slots__ = ("manifest", "module", "state")

    def __init__(self, manifest, module, state):
        self.manifest = manifest
        self.module = module
        self.state = state


class PluginRuntime:
    """插件目录的宿主。"""

    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self._plugins = {}

    def load_all(self):
        """装载目录里全部插件，返回按名字排序的插件名列表。

        中途任何一个插件失败都抛错，宿主维持装载前的样子。
        """
        staged = {}
        for plugin_name, path in self._scan():
            staged[plugin_name] = self._load_one(plugin_name, path)
        self._plugins = staged
        return sorted(staged)

    def _scan(self):
        if not os.path.isdir(self.plugin_dir):
            raise ReplugError("插件目录不存在: %s" % self.plugin_dir)
        found = []
        for entry in sorted(os.listdir(self.plugin_dir)):
            if entry.startswith("_") or not entry.endswith(".py"):
                continue
            found.append((entry[:-3], os.path.join(self.plugin_dir, entry)))
        return found

    def _load_one(self, plugin_name, path):
        module = load_module(path, plugin_name)
        manifest = parse_manifest(getattr(module, "PLUGIN", None), plugin_name, path)
        if not callable(getattr(module, "handle", None)):
            raise ManifestError("插件 %s 没有可调用的 handle" % plugin_name)
        context = PluginContext(manifest.name, manifest.version,
                                self.plugin_dir, path)
        state = None
        init = getattr(module, "init", None)
        if callable(init):
            try:
                state = init(context)
            except Exception as exc:
                raise InitError("插件 %s 初始化失败: %s" % (plugin_name, exc)) from exc
        return _Plugin(manifest, module, state)

    def request(self, plugin_name, request):
        """把一条请求交给插件处理，返回 handle 的返回值。"""
        plugin = self._lookup(plugin_name)
        try:
            return plugin.module.handle(plugin.state, request)
        except Exception as exc:
            raise PluginError("插件 %s 处理请求失败: %s"
                              % (plugin_name, exc)) from exc

    def _lookup(self, plugin_name):
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise PluginNotFound("插件 %s 不在宿主里" % plugin_name)
        return plugin

    def plugin_names(self):
        """已装载插件的名字，排序。"""
        return sorted(self._plugins)

    def version_of(self, plugin_name):
        return self._lookup(plugin_name).manifest.version

    def manifest_of(self, plugin_name):
        return self._lookup(plugin_name).manifest

    def state_of(self, plugin_name):
        """插件实例状态。宿主不拷贝，拿到的是活对象。"""
        return self._lookup(plugin_name).state
