"""pluginhost: 进程内插件宿主。

插件实现 Plugin 基类挂到 PluginHost 上，宿主按 priority 升序调度
钩子。注册约定、dispatch 语义与错误行为见 README。
"""

from pluginhost.host import PluginHost
from pluginhost.plugin import Plugin

__all__ = ["Plugin", "PluginHost"]
