"""actorbox: 一个朴素的消息分发小库，纯标准库，无外部依赖。

现阶段只有同步的一层：Registry 记住名字到处理器的映射，send 就在
调用方线程里直接把消息递给处理器并把返回值带回来。同名字可以一起
跑，但没有邮箱、没有排队、没有生命周期，也谈不上异步、监督与死信。
"""

from .registry import (
    ActorError,
    DuplicateActor,
    HandlerError,
    NoSuchActor,
    Registry,
)

__all__ = [
    "ActorError",
    "DuplicateActor",
    "HandlerError",
    "NoSuchActor",
    "Registry",
]
