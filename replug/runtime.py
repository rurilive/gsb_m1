"""插件宿主：从目录装载插件，把请求派发给插件处理。

一次性装载：load_all 把插件目录里所有 py 文件读进来，校验清单、按依赖
顺序调 init 建状态，装完就位。要么全部成功，要么一点不动地维持原样并
抛错。

热重载：reload(name) 只重读一个插件文件，新版本定义了 migrate(old_state)
就把旧状态的副本交给它迁移，没有 migrate 就照带旧状态。导入、初始化、
迁移任一步抛错，整次重载作废：旧模块、旧状态继续服务，在途请求不断。
切换是一次性换引用，多线程下不会拿到新旧拼起来的插件。
"""

import copy
import heapq
import os
import sys
import threading

from replug.errors import (InitError, ManifestError, MigrateError,
                           PluginError, PluginNotFound, ReplugError)
from replug.loader import load_module, module_name_for
from replug.manifest import parse_manifest

_MISSING = object()


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

    __slots__ = ("manifest", "module", "state", "path", "generation")

    def __init__(self, manifest, module, state, path, generation=0):
        self.manifest = manifest
        self.module = module
        self.state = state
        self.path = path
        self.generation = generation


class PluginRuntime:
    """插件目录的宿主。"""

    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self._plugins = {}
        self._generation = 0
        # _lock 护住插件表；_commit_lock 把装载/重载的“准备+换表”串行化。
        self._lock = threading.RLock()
        self._commit_lock = threading.Lock()

    def load_all(self):
        """装载目录里全部插件，返回按名字排序的插件名列表。

        按 requires 的依赖顺序初始化。中途任何一个插件失败都抛错，宿主
        维持装载前的样子：老插件、老状态一个不动，sys.modules 也还原。
        """
        with self._commit_lock:
            scanned = self._scan()
            module_snapshots = {}
            staged = {}
            try:
                manifests = {}
                for plugin_name, path in scanned:
                    module = self._stage_module(module_snapshots,
                                                plugin_name, path)
                    manifest = parse_manifest(
                        getattr(module, "PLUGIN", None), plugin_name, path)
                    self._check_handle(module, plugin_name)
                    manifests[plugin_name] = manifest
                    staged[plugin_name] = (module, manifest, path)
                order = topo_order(manifests)
                entries = {}
                for plugin_name in order:
                    module, manifest, path = staged[plugin_name]
                    state = self._fresh_state(module, manifest, path)
                    entries[plugin_name] = _Plugin(
                        manifest, module, state, path)
                self._commit_all(entries)
            except BaseException:
                self._restore_modules(module_snapshots)
                raise
            return sorted(entries)

    def reload(self, plugin_name):
        """热重载一个已装载插件，不重启、不动其他插件。

        新版本有可调用的 migrate(old_state) 时，把旧状态的深拷贝交给它，
        其返回值作为新状态；没有 migrate 就照带旧状态。插件清单里新出现
        且宿主还没有的依赖会一并从磁盘补齐；被依赖的其他插件不自动重载。

        导入、迁移或初始化任一步抛错，整次重载作废：旧版本继续服务，
        旧状态不被修改，在途请求不断。成功时换表是原子的，请求线程
        不可能看到新旧混用的一份插件。
        """
        with self._commit_lock:
            with self._lock:
                old_plugin = self._plugins.get(plugin_name)
                if old_plugin is None:
                    raise PluginNotFound(
                        "插件 %s 不在宿主里，无法重载" % plugin_name)
                old_plugins = dict(self._plugins)

            module_snapshots = {}
            staged = {}
            try:
                manifests = {name: plugin.manifest
                             for name, plugin in old_plugins.items()
                             if name != plugin_name}

                target_module = self._stage_module(
                    module_snapshots, plugin_name, old_plugin.path)
                target_manifest = parse_manifest(
                    getattr(target_module, "PLUGIN", None),
                    plugin_name, old_plugin.path)
                self._check_handle(target_module, plugin_name)
                manifests[plugin_name] = target_manifest
                staged[plugin_name] = (target_module, target_manifest,
                                       old_plugin.path)

                # 新版本 requires 链上若有宿主还没装过的插件，从磁盘补齐。
                pending = list(target_manifest.requires)
                traversed = set(manifests)
                while pending:
                    required = pending.pop()
                    if required in traversed:
                        continue
                    traversed.add(required)
                    if required in old_plugins:
                        pending.extend(
                            old_plugins[required].manifest.requires)
                        continue
                    path = os.path.join(self.plugin_dir, required + ".py")
                    module = self._stage_module(
                        module_snapshots, required, path)
                    manifest = parse_manifest(
                        getattr(module, "PLUGIN", None), required, path)
                    self._check_handle(module, required)
                    manifests[required] = manifest
                    staged[required] = (module, manifest, path)
                    pending.extend(manifest.requires)

                order = topo_order(manifests)
                entries = {}
                for name in order:
                    if name not in staged:
                        continue
                    module, manifest, path = staged[name]
                    if name == plugin_name:
                        state = self._migrated_state(
                            old_plugin, module, manifest, path)
                    else:
                        state = self._fresh_state(module, manifest, path)
                    entries[name] = _Plugin(manifest, module, state, path)
                self._commit_reload(plugin_name, old_plugin, entries)
            except BaseException:
                self._restore_modules(module_snapshots)
                raise

    def _scan(self):
        if not os.path.isdir(self.plugin_dir):
            raise ReplugError("插件目录不存在: %s" % self.plugin_dir)
        found = []
        for entry in sorted(os.listdir(self.plugin_dir)):
            if entry.startswith("_") or not entry.endswith(".py"):
                continue
            found.append((entry[:-3], os.path.join(self.plugin_dir, entry)))
        return found

    def _stage_module(self, snapshots, plugin_name, path):
        """导入一个插件模块，登记 sys.modules 旧值，供失败时整体还原。"""
        registered_name = module_name_for(plugin_name)
        if registered_name not in snapshots:
            snapshots[registered_name] = sys.modules.get(
                registered_name, _MISSING)
        return load_module(path, plugin_name)

    @staticmethod
    def _restore_modules(snapshots):
        for registered_name, previous in snapshots.items():
            if previous is _MISSING:
                sys.modules.pop(registered_name, None)
            else:
                sys.modules[registered_name] = previous

    @staticmethod
    def _check_handle(module, plugin_name):
        if not callable(getattr(module, "handle", None)):
            raise ManifestError("插件 %s 没有可调用的 handle" % plugin_name)

    def _context(self, manifest, path):
        return PluginContext(manifest.name, manifest.version,
                             self.plugin_dir, path)

    def _fresh_state(self, module, manifest, path):
        init = getattr(module, "init", None)
        if not callable(init):
            return None
        try:
            return init(self._context(manifest, path))
        except Exception as exc:
            raise InitError("插件 %s 初始化失败: %s"
                            % (manifest.name, exc)) from exc

    def _migrated_state(self, old_plugin, module, manifest, path):
        """按新版本要求接旧状态；全程不碰活的旧状态对象。"""
        migrate = getattr(module, "migrate", None)
        if not callable(migrate):
            return old_plugin.state
        try:
            working_state = copy.deepcopy(old_plugin.state)
        except Exception as exc:
            raise MigrateError("插件 %s 状态拷贝失败: %s"
                               % (manifest.name, exc)) from exc
        try:
            return migrate(working_state)
        except Exception as exc:
            raise MigrateError("插件 %s 状态迁移失败: %s"
                               % (manifest.name, exc)) from exc

    def _commit_all(self, entries):
        with self._lock:
            self._generation += 1
            for entry in entries.values():
                entry.generation = self._generation
            self._plugins = entries

    def _commit_reload(self, plugin_name, old_plugin, entries):
        with self._lock:
            if self._plugins.get(plugin_name) is not old_plugin:
                raise ReplugError(
                    "插件 %s 在重载准备期间已被更换，本次重载作废"
                    % plugin_name)
            self._generation += 1
            for entry in entries.values():
                entry.generation = self._generation
            self._plugins.update(entries)

    def request(self, plugin_name, request):
        """把一条请求交给插件处理，返回 handle 的返回值。"""
        with self._lock:
            plugin = self._lookup(plugin_name)
        # 拿到的是不可变实例引用：锁外慢慢跑也只碰这一版，重载换表与
        # 在途请求互不影响，更不会新旧混用。
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

    def consistency_report(self):
        """各插件与其依赖是否同代，返回 {插件名: [落后于它的依赖...]}。

        只重载被依赖者时，依赖方不会自动重载，它就落后了：这里列出它
        整条依赖链上代际更新的依赖。全部一致时值全为空列表。
        """
        with self._lock:
            snapshot = {
                name: (tuple(plugin.manifest.requires), plugin.generation)
                for name, plugin in self._plugins.items()
            }
        report = {}
        for name in sorted(snapshot):
            own_requires, own_generation = snapshot[name]
            stale = []
            seen = set()
            pending = list(own_requires)
            while pending:
                required = pending.pop()
                if required in seen:
                    continue
                seen.add(required)
                info = snapshot.get(required)
                if info is None:
                    stale.append(required)
                else:
                    requires, generation = info
                    if generation > own_generation:
                        stale.append(required)
                    pending.extend(requires)
            report[name] = sorted(set(stale))
        return report


def topo_order(manifests):
    """按 requires 排出初始化顺序，名字字典序兜底；有环或缺依赖报错。"""
    indegree = {name: 0 for name in manifests}
    dependents = {name: [] for name in manifests}
    for name, manifest in manifests.items():
        for required in manifest.requires:
            if required == name:
                raise ManifestError("插件 %s 依赖自己" % name)
            if required not in manifests:
                raise ManifestError(
                    "插件 %s 依赖的 %s 不在插件目录里" % (name, required))
            indegree[name] += 1
            dependents[required].append(name)
    ready = [name for name, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for dependent in dependents[name]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)
    if len(order) != len(manifests):
        remaining = sorted(name for name, degree in indegree.items()
                           if degree > 0)
        raise ManifestError("插件依赖有环: %s" % ", ".join(remaining))
    return order
