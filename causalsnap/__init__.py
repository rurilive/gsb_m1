"""causalsnap: 多进程共享状态的进程内骨架。"""

from .store import CausalStore, Event

__all__ = ["CausalStore", "Event"]
