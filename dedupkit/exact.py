"""精确去重计数。

ExactCounter 把见过的 key 原样放进 set：add 报告这次的 key 是不是新的，
count 给不同 key 的个数。结果精确，代价是内存随不同 key 数线性增长。
"""

import threading


class ExactCounter:
    """基于 set 的精确去重计数器，单次操作线程安全。"""

    def __init__(self):
        self._keys = set()
        self._lock = threading.Lock()

    def add(self, key):
        """记一个 key；首次出现返回 True，重复出现返回 False。"""
        with self._lock:
            if key in self._keys:
                return False
            self._keys.add(key)
            return True

    def count(self):
        """当前不同 key 的个数。"""
        with self._lock:
            return len(self._keys)

    def keys(self):
        """把当前 key 拷一份出来，供导出与迁移使用。"""
        with self._lock:
            return tuple(self._keys)

    def __contains__(self, key):
        """key 是否出现过。"""
        with self._lock:
            return key in self._keys

    def reset(self):
        """清空，回到空计数器状态。"""
        with self._lock:
            self._keys.clear()
