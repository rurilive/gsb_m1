"""cachex：固定容量的键值缓存，纯标准库，无外部依赖。"""

from .cache import Cache, CacheError, InvalidCapacityError, InvalidKeyError

__all__ = ["Cache", "CacheError", "InvalidCapacityError", "InvalidKeyError"]
