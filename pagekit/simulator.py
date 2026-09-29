"""页替换模拟器，纯标准库。

现有能力（基线）：

- 构造只要一个 capacity，容量是常驻帧数上限；
- access(page) 处理一次请求页号，页已在帧里算命中并返回 True，不在算缺失并返回 False；
- 缺失时把页装入一个空闲帧，没有空闲帧就按 LRU 淘汰最久未访问的常驻页；
- write(page) 处理一次带写的请求页号，命中就把该页标脏，缺失时装入后直接标脏；
- stats 给出容量、常驻页数、命中数、缺失数与淘汰数；
- resident 列出当前常驻页号，命中率 hit_ratio 是命中数除以命中数加缺失数。

当前只有单次访问的 LRU，没有访问历史，没有脏页写回，没有写回缓冲，
也没有预取。
"""


class PageSimulator:
    """请求页号驱动的页替换模拟器，淘汰策略是单次访问的 LRU。"""

    def __init__(self, capacity):
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._frames = {}
        self._seq = 0
        self._hits = 0
        self._misses = 0
        self._evicted = 0

    def _touch(self, member):
        self._seq += 1
        member["recency"] = self._seq

    def _evict_one(self):
        victim = None
        for page, member in self._frames.items():
            if victim is None or member["recency"] < self._frames[victim]["recency"]:
                victim = page
        del self._frames[victim]
        self._evicted += 1
        return victim

    def _install(self, page):
        if len(self._frames) >= self.capacity:
            self._evict_one()
        member = {"recency": 0, "dirty": False}
        self._touch(member)
        self._frames[page] = member

    def access(self, page):
        """处理一次请求页号。命中返回 True，缺失返回 False。"""
        if page in self._frames:
            self._touch(self._frames[page])
            self._hits += 1
            return True
        self._install(page)
        self._misses += 1
        return False

    def write(self, page):
        """处理一次带写的请求页号。命中把该页标脏，缺失时装入后标脏。"""
        if page in self._frames:
            member = self._frames[page]
            member["dirty"] = True
            self._touch(member)
            self._hits += 1
            return True
        self._install(page)
        self._frames[page]["dirty"] = True
        self._misses += 1
        return False

    def resident(self):
        """当前常驻页号列表，按最近使用次序从早到晚。"""
        order = sorted(self._frames, key=lambda p: self._frames[p]["recency"])
        return list(order)

    def stats(self):
        """当前统计：容量、常驻页数、命中、缺失与淘汰数。"""
        return {
            "capacity": self.capacity,
            "resident": len(self._frames),
            "hits": self._hits,
            "misses": self._misses,
            "evicted": self._evicted,
        }

    def hit_ratio(self):
        """命中率，命中数除以命中数加缺失数；总请求为零时返回零。"""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    def __len__(self):
        return len(self._frames)

    def __contains__(self, page):
        return page in self._frames
