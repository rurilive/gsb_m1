"""buskit: 内存消息代理。

当前只提供一个最简单的发布订阅，见 buskit/broker.py（MessageBus）。
确认机制、未确认重投、过滤、背压与回放见任务描述。
"""

from buskit.broker import MessageBus, Message

__all__ = ["MessageBus", "Message"]