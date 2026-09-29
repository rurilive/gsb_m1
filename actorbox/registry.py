"""actorbox 的现有实现。

当前只有一套朴素的名字到处理器的映射：注册一个名字与一个可调用对象，
send 在调用方线程里同步地把消息交给处理器，返回值原样带回来。处理器
抛异常就原样向上抛。没有邮箱、没有排队、没有顺序保证、没有生命周期，
也没有监督与死信。处理器必须是可调用的，否则在注册处就拒绝。
"""


class ActorError(Exception):
    """actorbox 所有公开错误的基类。"""


class DuplicateActor(ActorError):
    """同名 actor 已经注册过。"""


class NoSuchActor(ActorError):
    """按名字找不到目标 actor。"""


class HandlerError(ActorError):
    """处理器在同步调用中抛出的异常，原始异常挂在 __cause__ 上。"""


class Registry:
    """名字到处理器的同步映射。

    没有邮箱，也没有后台处理线程：send 直接在调用方线程里执行处理器，
    调用返回就代表处理器已经跑完。
    """

    def __init__(self):
        self._handlers = {}

    def register(self, name, handler):
        """注册一个名字与处理器，名字重复或处理器不可调用都直接拒绝。"""
        if not isinstance(name, str) or not name:
            raise ActorError("name must be a non-empty str")
        if not callable(handler):
            raise ActorError("handler must be callable")
        if name in self._handlers:
            raise DuplicateActor(name)
        self._handlers[name] = handler
        return name

    def unregister(self, name):
        """摘掉一个已注册的名字，名字不存在时拒绝。"""
        if name not in self._handlers:
            raise NoSuchActor(name)
        del self._handlers[name]

    def has(self, name):
        """名字当前是否已注册。"""
        return name in self._handlers

    def names(self):
        """当前已注册的名字，按注册顺序给出。"""
        return list(self._handlers)

    def send(self, name, message):
        """同步地把消息交给处理器，返回处理器的返回值。

        处理器不存在抛 NoSuchActor；处理器自身抛异常则原样包装成
        HandlerError 向上抛，避免把内部栈信息直接泄漏给调用方，
        但保留 __cause__ 供排查。
        """
        if name not in self._handlers:
            raise NoSuchActor(name)
        handler = self._handlers[name]
        try:
            return handler(message)
        except ActorError:
            raise
        except Exception as exc:  # noqa: BLE001 - 如实包装处理器异常
            raise HandlerError(name) from exc
