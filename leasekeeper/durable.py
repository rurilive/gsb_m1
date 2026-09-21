"""带日志的租约发放台：幂等发放、记号跨重启续发、按到期回收。

在 LeaseKeeper 的语义上加三件事，老调用一律不动：

- 幂等发放：grant 可带 request_id，请求标识跟着重试走，租约还活着期
  间同一标识的重试拿回同一份租约，不会发成两份；并发重试也只发一次。
- 崩溃恢复：grant 先追加日志并 fsync 再发号，重启从日志续记号（只增
  不减），并按资源把历史高水位回灌 FenceGuard，旧纪元的记号过不了存
  储层。重启那刻没归还的租约一律按回收处理——单调钟跨进程不可比，
  留着也判不了期——恢复时计入回收，同资源不会有两份活租约。
- 热路径不碰盘：renew 走 lease_id 直索引加到期小顶堆，纯内存 O(1)；
  sweep 只弹出当轮真到期的条目，开销与全表规模无关。
"""

import heapq
import os
import time
from dataclasses import replace

from leasekeeper.clock import MonotonicClamp
from leasekeeper.keeper import Lease, LeaseConflict, LeaseKeeper


class DurableKeeper(LeaseKeeper):
    """带幂等与崩溃恢复的租约发放台，语义与 LeaseKeeper 一致。

    clock: 单调时钟，外面再套一层 MonotonicClamp，回拨被钳住。
    journal: grant/release 日志路径，None 表示纯内存（不保证跨重启）。
    fence: 可选 FenceGuard，发号后把该资源高水位灌进去，重启时先把恢
    复出的高水位回灌，旧记号从此过不了闸门。
    """

    def __init__(self, clock=time.monotonic, journal=None, fence=None):
        super().__init__(clock=MonotonicClamp(clock).current)
        self._by_id = {}     # lease_id -> 租约，续期直查
        self._heap = []      # (expires_at, token, lease_id) 小顶堆，懒删除
        self._reqs = {}      # request_id -> lease_id，幂等台账
        self._water = {}     # resource -> 历史最高记号
        self._journal = journal
        self._fence = fence
        if journal is not None:
            self._recover()
        if fence is not None:
            self.seal_fence(fence)

    def grant(self, resource, holder, ttl=30.0, request_id=None):
        """发租约，语义同 LeaseKeeper.grant；request_id 让重试幂等。

        同一 request_id 在租约还活着期间重试（含并发重试），拿回当初那
        份租约，不重复发号、不计发放数；租约已过期或已归还则标识失效，
        按一次新发放处理。发放先把记录追加进日志并 fsync，再改内存。
        """
        ttl = float(ttl)
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        with self._lock:
            now = self._clock()
            if request_id is not None:
                lease_id = self._reqs.get(request_id)
                if lease_id is not None:
                    lease = self._by_id.get(lease_id)
                    if lease is not None and now < lease.expires_at:
                        return lease
                    del self._reqs[request_id]
            old = self._leases.get(resource)
            if old is not None:
                if now < old.expires_at:
                    self._conflicts += 1
                    raise LeaseConflict(
                        "resource still leased: %r" % (resource,)
                    )
                self._drop(old)
                self._reclaims += 1
            token = self._next_token
            self._next_token += 1
            lease = Lease(
                lease_id="L%06d" % token,
                resource=resource,
                holder=holder,
                token=token,
                ttl=ttl,
                expires_at=now + ttl,
            )
            self._append(
                "G\t%d\t%s\t%s\t%g" % (token, resource, holder, ttl),
                sync=True,
            )
            self._leases[resource] = lease
            self._by_id[lease.lease_id] = lease
            heapq.heappush(
                self._heap, (lease.expires_at, token, lease.lease_id)
            )
            if request_id is not None:
                self._reqs[request_id] = lease.lease_id
            self._water[resource] = token
            if self._fence is not None:
                self._fence.seal(resource, token)
            self._grants += 1
            return lease

    def renew(self, lease_id, holder, ttl=None):
        """续期，语义同 LeaseKeeper.renew；直索引 O(1)，不碰磁盘。"""
        if ttl is not None:
            ttl = float(ttl)
            if ttl <= 0:
                raise ValueError("ttl must be positive")
        with self._lock:
            lease = self._by_id.get(lease_id)
            if lease is None or lease.holder != holder:
                return None
            now = self._clock()
            if now >= lease.expires_at:
                self._drop(lease)
                self._reclaims += 1
                return None
            extend = lease.ttl if ttl is None else ttl
            renewed = replace(lease, ttl=extend, expires_at=now + extend)
            self._leases[lease.resource] = renewed
            self._by_id[lease_id] = renewed
            heapq.heappush(
                self._heap, (renewed.expires_at, renewed.token, lease_id)
            )
            self._renews += 1
            return renewed

    def release(self, lease_id, holder):
        """提前归还，语义同 LeaseKeeper.release；日志记一笔，丢失无害。"""
        with self._lock:
            lease = self._by_id.get(lease_id)
            if lease is None or lease.holder != holder:
                return False
            self._drop(lease)
            self._append(
                "R\t%s\t%d" % (lease.resource, lease.token), sync=False
            )
            self._releases += 1
            return True

    def get(self, resource):
        """资源当前的活租约，没有或已过期返回 None；过期顺手清掉。"""
        with self._lock:
            lease = self._leases.get(resource)
            if lease is None:
                return None
            if self._clock() >= lease.expires_at:
                self._drop(lease)
                self._reclaims += 1
                return None
            return lease

    def sweep(self):
        """清掉当轮真到期的租约，按资源名排序返回。

        开销只跟到期条数挂钩：从到期堆顶往外弹，弹到没到期就停；续期、
        归还留下的陈旧堆项顺手丢弃，均摊不进热路径。
        """
        with self._lock:
            now = self._clock()
            dead = []
            heap = self._heap
            by_id = self._by_id
            leases = self._leases
            heappop = heapq.heappop
            while heap and heap[0][0] <= now:
                expires_at, _, lease_id = heappop(heap)
                lease = by_id.get(lease_id)
                if lease is None or lease.expires_at != expires_at:
                    continue
                del leases[lease.resource]
                del by_id[lease_id]
                dead.append(lease)
            self._reclaims += len(dead)
            return sorted(dead, key=lambda l: l.resource)

    def high_water(self):
        """各资源历史最高记号的快照，重启后从日志恢复。"""
        with self._lock:
            return dict(self._water)

    def seal_fence(self, guard):
        """把各资源历史高水位灌进 FenceGuard，只涨不降。"""
        with self._lock:
            water = dict(self._water)
        for resource, token in water.items():
            guard.seal(resource, token)

    def _drop(self, lease):
        del self._leases[lease.resource]
        self._by_id.pop(lease.lease_id, None)

    def _append(self, line, sync):
        if self._journal is None:
            return
        with open(self._journal, "a") as fh:
            fh.write(line + "\n")
            fh.flush()
            if sync:
                os.fsync(fh.fileno())

    def _recover(self):
        """重放日志：续记号、算各资源高水位、回收没归还的租约。

        G 记发放，R 记归还；资源最后一笔是 G 且没有对应 R，说明崩溃那
        刻租约还没还，一律按回收处理。重放完把日志压实成 T（最后记号）
        加 W（各资源高水位）的头，之后的记录继续追加。
        """
        last = 0
        water = {}
        live = {}
        if os.path.exists(self._journal):
            with open(self._journal) as fh:
                for line in fh:
                    parts = line.rstrip("\n").split("\t")
                    if parts[0] == "G":
                        token = int(parts[1])
                        resource = parts[2]
                        if token > last:
                            last = token
                        if token > water.get(resource, 0):
                            water[resource] = token
                        live[resource] = token
                    elif parts[0] == "R":
                        if live.get(parts[1]) == int(parts[2]):
                            del live[parts[1]]
                    elif parts[0] == "T":
                        if int(parts[1]) > last:
                            last = int(parts[1])
                    elif parts[0] == "W":
                        token = int(parts[2])
                        if token > water.get(parts[1], 0):
                            water[parts[1]] = token
        self._next_token = last + 1
        self._water = water
        self._reclaims += len(live)
        if last or water:
            tmp = self._journal + ".tmp"
            with open(tmp, "w") as fh:
                fh.write("T\t%d\n" % last)
                for resource in sorted(water):
                    fh.write("W\t%s\t%d\n" % (resource, water[resource]))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._journal)
