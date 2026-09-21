"""插件宿主：从目录装载插件，把请求派发给插件处理。

一次性装载：load_all 把插件目录里所有 py 文件读进来，校验清单、按
requires 依赖序调 init 建状态，装完就位。要么全部成功，要么一点不动地
维持原样并抛错。

热重载：reload(name) 只重读一个插件文件。新版模块定义了 migrate(old)
就把旧状态的深拷贝交给它，返回值当新状态；没定义就连旧状态一起带过去。
导入、初始化（init 在全新装载时）、迁移任一步抛错，整次重载作废：旧版本
继续服务、旧状态原样保留。切换只在最后一步替换一个引用，是原子的；所有
派发与查询都走同一把锁，在途请求引用的是开始时拿到的插件快照，不会新旧
混用、也不会被重载打断。
"""

import copy
import os
import sys
import threading

from replug.errors import (InitError, ManifestError, MigrateError,
                           PluginError, PluginNotFound, ReplugError)
from replug.loader import load_module, module_name_for
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

    __slots__ = ("manifest", "module", "state", "generation")

    def __init__(self, manifest, module, state, generation=0):
        self.manifest = manifest
        self.module = module
        self.state = state
        self.generation = generation


class PluginRuntime:
    """插件目录的宿主。"""

    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self._plugins = {}
        self._lock = threading.RLock()
        self._generation = 0

    @staticmethod
    def _ordered(manifests):
        """按 requires 依赖序排出插件名：被依赖者排在前面。

        requires 指向不存在的插件或依赖成环都报 ManifestError。
        """
        for name, manifest in manifests.items():
            for dep in manifest.requires:
                if dep not in manifests:
                    raise ManifestError(
                        "插件 %s 依赖的 %s 不在插件目录里" % (name, dep))
        order = []
        visiting = set()

        def visit(name):
            if name in visiting:
                raise ManifestError("插件依赖里有环，涉及 %s" % name)
            if name in order:
                return
            visiting.add(name)
            for dep in manifests[name].requires:
                visit(dep)
            visiting.remove(name)
            order.append(name)

        for name in sorted(manifests):
            visit(name)
        return order

    def _import_candidate(self, plugin_name, path, allowed):
        """导入一个插件并校验清单，requires 必须落在 allowed 里。

        只做单点校验；缺依赖、依赖成环交给之后统一的 _ordered。
        返回 _Plugin 骨架（state 还是 None、generation 未设置）。
        """
        module = load_module(path, plugin_name)
        manifest = parse_manifest(getattr(module, "PLUGIN", None),
                                  plugin_name, path)
        if not callable(getattr(module, "handle", None)):
            raise ManifestError("插件 %s 没有可调用的 handle" % plugin_name)
        for dep in manifest.requires:
            if dep not in allowed:
                raise ManifestError(
                    "插件 %s 依赖的 %s 不在宿主里" % (plugin_name, dep))
        return _Plugin(manifest, module, None)

    @staticmethod
    def _init_plugin(plugin, plugin_dir):
        """调插件 init 建状态，init 抛错包成 InitError。"""
        context = PluginContext(plugin.manifest.name, plugin.manifest.version,
                                plugin_dir, plugin.module.__file__)
        init = getattr(plugin.module, "init", None)
        if callable(init):
            try:
                plugin.state = init(context)
            except Exception as exc:
                raise InitError("插件 %s 初始化失败: %s"
                                % (plugin.manifest.name, exc)) from exc

    def _rollback_module(self, old, plugin_name):
        """新模块没切上去：把 sys.modules 恢复成旧模块。"""
        sys.modules.pop(module_name_for(plugin_name), None)
        if old is not None:
            sys.modules[module_name_for(plugin_name)] = old.module

    def load_all(self):
        """装载目录里全部插件，返回按名字排序的插件名列表。

        先把所有插件导入、清单校验、依赖排序做完，再按依赖序调 init；
        中途任何一步失败都抛错，宿主维持装载前的样子（一个插件都不换）。
        """
        scanned = self._scan()
        with self._lock:
            candidates = {}
            for plugin_name, path in scanned:
                plugin = self._import_candidate(
                    plugin_name, path, allowed={n for n, _ in scanned})
                candidates[plugin_name] = plugin
            order = self._ordered(
                {name: plugin.manifest for name, plugin in candidates.items()})
            self._generation += 1
            generation = self._generation
            for plugin_name in order:
                plugin = candidates[plugin_name]
                self._init_plugin(plugin, self.plugin_dir)
                plugin.generation = generation
            self._plugins = candidates
            return sorted(candidates)

    def _scan(self):
        if not os.path.isdir(self.plugin_dir):
            raise ReplugError("插件目录不存在: %s" % self.plugin_dir)
        found = []
        for entry in sorted(os.listdir(self.plugin_dir)):
            if entry.startswith("_") or not entry.endswith(".py"):
                continue
            found.append((entry[:-3], os.path.join(self.plugin_dir, entry)))
        return found

    def reload(self, plugin_name):
        """热重载单个插件，不重启宿主，返回新版版本号。

        新版有 migrate(old_state) 就把旧状态的深拷贝交给它，返回值当新
        状态；没有就把旧状态原样带到新版。导入、迁移任一步抛错，本次重载
        整次作废：旧版本继续服务，旧状态一个字节不改。被本插件依赖或
        依赖本插件的其他插件都不会被动到，用 consistency_report() 查看
        因此产生的版本不一致。
        """
        with self._lock:
            old = self._plugins.get(plugin_name)
            if old is None:
                raise PluginNotFound("插件 %s 不在宿主里" % plugin_name)
            path = old.module.__file__
            if not os.path.isfile(path):
                raise ReplugError("插件 %s 源文件不在了: %s"
                                  % (plugin_name, path))
            try:
                candidate = self._import_candidate(
                    plugin_name, path, allowed=set(self._plugins))
                graph = {name: plugin.manifest
                         for name, plugin in self._plugins.items()}
                graph[plugin_name] = candidate.manifest
                self._ordered(
                    graph)
                old_state = old.state
                try:
                    state_copy = copy.deepcopy(old_state)
                except Exception as exc:
                    raise MigrateError(
                        "插件 %s 的旧状态无法复制: %s"
                        % (plugin_name, exc)) from exc
                migrate = getattr(candidate.module, "migrate", None)
                if callable(migrate):
                    try:
                        candidate.state = migrate(state_copy)
                    except Exception as exc:
                        raise MigrateError(
                            "插件 %s 状态迁移失败: %s"
                            % (plugin_name, exc)) from exc
                else:
                    candidate.state = state_copy
                self._generation += 1
                candidate.generation = self._generation
            except Exception:
                self._rollback_module(old, plugin_name)
                raise
            self._plugins[plugin_name] = candidate
            return candidate.manifest.version

    def request(self, plugin_name, request):
        """把一条请求交给插件处理，返回 handle 的返回值。"""
        with self._lock:
            plugin = self._lookup(plugin_name)
            try:
                return plugin.module.handle(plugin.state, request)
            except Exception as exc:
                raise PluginError("插件 %s 处理请求失败: %s"
                                  % (plugin_name, exc)) from exc

    def consistency_report(self):
        """报告重载导致的版本不一致：{插件名: [该先对齐的相邻插件...]}。

        reload 只换被点名的插件，不级联。requires 边的任一端比另一端新，
        旧的那一端就不一致：旧版被依赖方会拖累依赖它的插件，旧版依赖方
        没跟上被它依赖的新插件。空字典表示全宿主版本同代、完全一致。
        """
        with self._lock:
            plugins = dict(self._plugins)
        report = {}
        for name in sorted(plugins):
            generation = plugins[name].generation
            stale = set()
            for dep in plugins[name].manifest.requires:
                target = plugins.get(dep)
                if target is not None and target.generation > generation:
                    stale.add(dep)
            for other_name, other in plugins.items():
                if (name in other.manifest.requires
                        and other.generation > generation):
                    stale.add(other_name)
            if stale:
                report[name] = sorted(stale)
        return report

    def _lookup(self, plugin_name):
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise PluginNotFound("插件 %s 不在宿主里" % plugin_name)
        return plugin

    def plugin_names(self):
        """已装载插件的名字，排序。"""
        with self._lock:
            return sorted(self._plugins)

    def version_of(self, plugin_name):
        with self._lock:
            return self._lookup(plugin_name).manifest.version

    def manifest_of(self, plugin_name):
        with self._lock:
            return self._lookup(plugin_name).manifest

    def state_of(self, plugin_name):
        """插件实例状态。宿主不拷贝，拿到的是活对象。"""
        with self._lock:
            return self._lookup(plugin_name).state
