"""分配计数。

口径：
- acquisitions / releases 记次数，bytes_acquired 是请求容量之和
- live 是在借数量，peak_live 是在借峰值
- tier_counts 按档位记 acquire 次数，超出最大档位的记在 oversize
"""

import threading

from bufpool.tiers import tier_key


class AllocStats:
    """分配器的计数账本，可跨线程更新。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.acquisitions = 0
        self.releases = 0
        self.bytes_acquired = 0
        self.live = 0
        self.peak_live = 0
        self.tier_counts = {}

    def record_acquire(self, size):
        key = tier_key(size)
        with self._lock:
            self.acquisitions += 1
            self.bytes_acquired += size
            self.live += 1
            if self.live > self.peak_live:
                self.peak_live = self.live
            self.tier_counts[key] = self.tier_counts.get(key, 0) + 1

    def record_release(self, size):
        with self._lock:
            self.releases += 1
            self.live -= 1

    def snapshot(self):
        """一次性取走当前计数，后面对账本的操作不影响这份快照。"""
        with self._lock:
            return {
                "acquisitions": self.acquisitions,
                "releases": self.releases,
                "bytes_acquired": self.bytes_acquired,
                "live": self.live,
                "peak_live": self.peak_live,
                "tier_counts": dict(self.tier_counts),
            }
