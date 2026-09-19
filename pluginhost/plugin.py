"""插件基类与调用约定。

宿主按 priority 升序调用插件的同名钩子，priority 相同时按注册先后。
钩子分两类：业务钩子经 dispatch(hook, payload) 调用，返回值沿插件链
传递；生命周期回调由宿主在固定时机直接触发。
"""


class Plugin:
    """插件基类，子类按需覆盖钩子方法。

    类属性：
    - name: 插件名，宿主内唯一，注册时校验
    - priority: 调用顺序，小的先调用，默认 100
    """

    name = ""
    priority = 100

    def on_registered(self, host):
        """注册完成后的生命周期回调，可以在这里保存 host 引用。"""

    def on_message(self, message):
        """业务钩子示例：返回替换后的消息，返回 None 表示透传原消息。"""
        return None
