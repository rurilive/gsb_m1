"""topichub: 内存主题订阅代理。

当前只提供最朴素的一对一回调注册与直接调用，见 topichub/hub.py。
多主题分发、通配主题、订阅过滤、至少一次投递与确认重投、背压与退订
见任务描述。
"""

from topichub.hub import Message, Subscription, TopicHub

__all__ = ["TopicHub", "Message", "Subscription"]
