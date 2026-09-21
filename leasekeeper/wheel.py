"""按到期槽组织的回收轮：sweep 只花在真到期的桶上。

朴素实现拿一张 dict 装全部租约，每轮巡检把整张表过一遍，两万活跃租约
里只到期二十条也得付两万次比较。这里把到期时刻按 tick 秒量化进槽位：
槽位 -> 该槽到期的资源集合，另用一个小堆记非空槽，巡检只弹出到期槽。

关键在槽位懒建：同一槽位的 dict key 只在第一条租约落进去时建一次、
往堆里 push 一次，续期再多次也不重复入堆，所以每秒一万次续期不会把
堆泡大。槽内是集合，续租迁移时 O(1) 改挂，空槽留在 dict 里由 sweep
统一摘除（摘除后再次落租约会重新入堆一次）。
"""

import heapq
import math


class ExpiryWheel:
    """到期槽 + 非空槽小堆，桶粒度 tick 秒。"""

    def __init__(self, tick=1.0):
        tick = float(tick)
        if tick <= 0:
            raise ValueError("tick must be positive")
        self.tick = tick
        self._buckets = {}   # 槽位 -> 资源集合（空槽等 sweep 摘）
        self._nonempty = []  # 小堆：出现过非空租约的槽位

    def add(self, resource, expires_at):
        """把 resource 挂到 expires_at 对应的槽，返回槽位。"""
        slot = self._slot_of(expires_at)
        bucket = self._buckets.get(slot)
        if bucket is None:
            bucket = set()
            self._buckets[slot] = bucket
            heapq.heappush(self._nonempty, slot)
        bucket.add(resource)
        return slot

    def discard(self, resource, expires_at):
        """把 resource 从 expires_at 对应的槽摘掉，槽空了也先留着。"""
        slot = self._slot_of(expires_at)
        bucket = self._buckets.get(slot)
        if bucket is not None:
            bucket.discard(resource)

    def due_slots(self, now):
        """now 时刻已经到期的槽位（严格：槽上界 <= now 才算）。"""
        cutoff = int(math.floor(now / self.tick))
        due = []
        while self._nonempty and self._nonempty[0] <= cutoff:
            slot = heapq.heappop(self._nonempty)
            due.append(slot)
        return due

    def pop_due(self, now):
        """弹出并清空 now 时刻所有到期槽，返回里面的资源列表。

        只遍历真到期的槽；开销与到期槽数、槽内资源数（即真到期条数）
        挂钩，与活跃总量无关。空槽顺手摘除，之后再进租约会重新入堆。
        """
        expired = []
        for slot in self.due_slots(now):
            # 槽位已出堆，dict 里无论空不空都摘除：之后再有租约落进
            # 同一槽位会走懒建重新入堆，不会出现“槽在 dict 但不在堆”。
            bucket = self._buckets.pop(slot, None)
            if bucket:
                expired.extend(bucket)
                bucket.clear()
        return expired

    def __len__(self):
        """还挂在轮上的资源数（含已到期还没 pop 的）。"""
        return sum(len(bucket) for bucket in self._buckets.values())

    def _slot_of(self, expires_at):
        return int(math.ceil(float(expires_at) / self.tick))
