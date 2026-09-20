"""guardcache: 规则服务的进程内多级缓存。"""

from .cache import GuardCache, NotFound

__all__ = ["GuardCache", "NotFound"]
