"""PluginHost：插件的注册、排序与钩子调度。"""

from pluginhost.plugin import Plugin


class PluginHost:
    """插件宿主。

    v1 只提供注册与钩子调度：插件一旦注册就固定留在调用链上，
    钩子抛错会让整轮 dispatch 直接失败。
    """

    def __init__(self):
        self._plugins = []  # 已按 (priority, 注册序) 排好

    @property
    def plugins(self):
        """按调用顺序返回插件列表（副本，调用方改不动内部状态）。"""
        return list(self._plugins)

    def __contains__(self, plugin):
        return any(p is plugin for p in self._plugins)

    def __len__(self):
        return len(self._plugins)

    def plugin(self, name):
        """按名字取插件，不存在时抛 KeyError。"""
        for p in self._plugins:
            if p.name == name:
                return p
        raise KeyError(name)

    def register(self, plugin):
        """注册插件：校验、按 priority 插入、回调 on_registered。

        on_registered 抛错时注册回滚（插件不留在宿主上），异常原样上抛。
        """
        if not isinstance(plugin, Plugin):
            raise TypeError("register 需要 Plugin 实例")
        if not plugin.name:
            raise ValueError("插件缺少 name")
        if any(p.name == plugin.name for p in self._plugins):
            raise ValueError("插件名重复: %s" % plugin.name)
        self._insert(plugin)
        try:
            plugin.on_registered(self)
        except BaseException:
            self._plugins.remove(plugin)
            raise

    def _insert(self, plugin):
        # 按 priority 升序找插入点：同 priority 落在已有插件之后（注册先后）
        index = len(self._plugins)
        for i, existing in enumerate(self._plugins):
            if plugin.priority < existing.priority:
                index = i
                break
        self._plugins.insert(index, plugin)

    def dispatch(self, hook, payload):
        """把 payload 沿插件链依次喂给每个插件的同名钩子。

        - 迭代开始时对插件列表取快照
        - 插件没有定义该钩子（无可调用属性）时跳过
        - 钩子返回 None 表示透传当前 payload，否则返回值作为
          下一个插件的输入；最终返回值即 dispatch 的返回值
        - 任何插件抛错都原样上抛，排在后面的插件本轮不会被调用
        """
        for plugin in list(self._plugins):
            method = getattr(plugin, hook, None)
            if not callable(method):
                continue
            result = method(payload)
            if result is not None:
                payload = result
        return payload
