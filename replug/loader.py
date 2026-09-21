"""按文件路径导入插件模块。

每次导入都把源文件重新读一遍再编译，不走 __pycache__：插件文件在同一秒
里被反复替换、大小还没变，也要读到新内容。模块名按插件名固定成
_replug_plugin_<name> 注册在 sys.modules，导入中途抛错就把半成品摘干净。
插件应自包含：模块名带宿主前缀，插件之间不能靠 import 相互引用。
"""

import sys
import types

from replug.errors import LoadError


def module_name_for(plugin_name):
    return "_replug_plugin_" + plugin_name


def load_module(path, plugin_name):
    """从 path 读入插件模块，读不了、语法错或导入期抛错都报 LoadError。"""
    try:
        with open(path, "rb") as stream:
            source = stream.read()
    except OSError as exc:
        raise LoadError("插件 %s 源文件读不了: %s" % (plugin_name, exc)) from exc
    try:
        code = compile(source, path, "exec")
    except (SyntaxError, ValueError) as exc:
        raise LoadError("插件 %s 语法错误: %s" % (plugin_name, exc)) from exc
    name = module_name_for(plugin_name)
    module = types.ModuleType(name)
    module.__file__ = path
    previous = sys.modules.pop(name, None)
    sys.modules[name] = module
    try:
        exec(code, module.__dict__)
    except Exception as exc:
        sys.modules.pop(name, None)
        if previous is not None:
            sys.modules[name] = previous
        raise LoadError("插件 %s 导入失败: %s" % (plugin_name, exc)) from exc
    return module
