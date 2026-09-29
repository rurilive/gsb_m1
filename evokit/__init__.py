"""evokit: 记录领域事件并按事件重放状态的内存聚合。"""

from .aggregate import Aggregate, ConcurrencyError, Event

__all__ = ["Aggregate", "ConcurrencyError", "Event"]
