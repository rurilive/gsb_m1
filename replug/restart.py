"""全量重启参考实现。

每次调用都从头建一个宿主、重新装载插件目录、按序处理请求。
拿它给宿主任何时候的行为做语义对拍。
"""

from replug.runtime import PluginRuntime


def restart_process(plugin_dir, calls):
    """calls 是 (插件名, 请求) 序列，返回逐条处理的结果。

    等价于把宿主整个重启到插件目录当前的样子，再把这串请求打完。
    """
    runtime = PluginRuntime(plugin_dir)
    runtime.load_all()
    return [runtime.request(name, request) for name, request in calls]
