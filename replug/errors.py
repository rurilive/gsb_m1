"""replug 的异常类型。

ReplugError    所有异常的基类
ManifestError  PLUGIN 声明缺失或格式不对
LoadError      插件模块导入失败
InitError      插件 init 抛错（LoadError 的子类）
PluginNotFound 请求或查询的插件不在宿主里
PluginError    插件 handle 抛错，消息里带插件名
"""


class ReplugError(Exception):
    """replug 运行时错误。"""


class ManifestError(ReplugError):
    """插件模块的 PLUGIN 声明不合法。"""


class LoadError(ReplugError):
    """插件模块导入失败。"""


class InitError(LoadError):
    """插件 init 调用失败。"""


class PluginNotFound(ReplugError):
    """插件不在宿主里。"""


class PluginError(ReplugError):
    """插件处理请求时抛错。"""
