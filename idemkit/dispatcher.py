"""任务分发：注册处理器，按任务名同步执行。

handler 签名 fn(payload) -> 结果。结果必须能通过 JSON 往返，
这是任何持久化或重放机制的前提。
"""

import json
from typing import Callable, Dict, List


class UnknownTaskError(KeyError):
    """任务名未注册。"""


class NotSerializableError(TypeError):
    """handler 返回值无法 JSON 往返。"""


class Dispatcher:
    """按任务名注册 handler，dispatch 同步执行一次。"""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, task_name: str, fn: Callable) -> None:
        """注册处理器。重复注册抛 ValueError。"""
        if task_name in self._handlers:
            raise ValueError(f"task already registered: {task_name}")
        self._handlers[task_name] = fn

    def handlers(self) -> List[str]:
        """按注册顺序返回任务名列表副本。"""
        return list(self._handlers)

    def dispatch(self, task_name: str, payload):
        """同步执行一次任务，返回 handler 的返回值。

        结果必须能通过 JSON 往返（json.dumps 后再 json.loads
        与原值相等），否则抛 NotSerializableError；
        handler 抛出的异常原样上抛。
        """
        if task_name not in self._handlers:
            raise UnknownTaskError(task_name)
        result = self._handlers[task_name](payload)
        try:
            restored = json.loads(json.dumps(result))
        except (TypeError, ValueError) as exc:
            raise NotSerializableError(
                f"result not JSON serializable: {result!r}"
            ) from exc
        if restored != result:
            raise NotSerializableError(
                f"result not JSON round-trip safe: {result!r}"
            )
        return result
