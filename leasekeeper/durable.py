"""带幂等发号、崩溃恢复与按量回收的租约台。

相对内存版 keeper 的四个新能力，全部走新模块，老调用签名不动：

1. grant 多一个可选 request_id：同一请求标识的重试拿回同一份租约，
   撞车的请求重放仍是撞车，绝不发成两份。不传 request_id 行为同旧版。
2. grant/release 先写只追加日志再改内存；recover 重放日志续号、续活
   崩溃时还没到期也没归还的租约，过期的一律回收。续期不落日志（高峰
   每秒一万次，路径不碰磁盘），恢复时按发号时的原始到期时刻判活。
3. 记号跨重启只增：下一个记号接日志里的最大记号；每个资源历史最大记
   号作为高水位，seal_guard 一次性灌进 FenceGuard，旧纪元记号进不了
   存储层。
4. ExpiryWheel 按到期槽巡检，sweep 开销只跟当轮真到期条数挂钩；另对
   注入钟加单调钳制，钟被往回拨时沿用上一次读到的时刻，过期租约不会
   因为时钟回拨而凭空多活。
"""

import threading
import time
from dataclasses import replace

from leasekeeper.fence import FenceGuard
from leasekeeper.journal import MemoryJournal
from leasekeeper.keeper import KeeperStats, Lease, LeaseConflict
from leasekeeper.wheel import ExpiryWheel


_CONFLICT = object()


class DurableLeaseKeeper:
    """日志 + 到期轮版本的租约台，公开 API 与 LeaseKeeper 对齐。"""

    def __init__(self, clock=time.monotonic, journal=None, wheel_tick=1.0):
        self._clock_source = clock
        self._journal = journal if journal is not None else MemoryJournal()
        self._lock = threading.Lock()
        self._wheel = ExpiryWheel(tick=wheel_tick)
        self._leases = {}        # resource -> 租约（含未巡检的过期份）
        self._index = {}         # lease_id -> resource
        self._dedupe = {}        # request_id -> Lease 或 _CONFLICT
        self._high = {}          # resource -> 历史最大记号
        self._next_token = 1
        self._now_floor = None   # 时钟回拨钳制位
        self._grants = 0
        self._conflicts = 0
        self._renews = 0
        self._releases = 0
        self._reclaims = 0

    @classmethod
    def recover(cls, journal, clock=time.monotonic, wheel_tick=1.0):
        """从日志重放出一台租约台：续号、续活、高水位、幂等表全恢复。

        每个资源以最后一条 grant 为准，之后被 release 的不算；恢复当
        下已过原始到期时刻的直接回收，活下来的重新挂进到期轮。
        """
        keeper = cls(clock=clock, journal=journal, wheel_tick=wheel_tick)
        committed = {}
        released = set()
        max_token = 0
        for record in journal.replay():
            kind = record["event"]
            if kind == "grant":
                lease = _lease_from(record)
                committed[lease.resource] = lease
                max_token = max(max_token, lease.token)
                if record.get("request_id") is not None:
                    keeper._dedupe[record["request_id"]] = lease
                keeper._high[lease.resource] = max(
                    keeper._high.get(lease.resource, 0), lease.token
                )
                keeper._grants += 1
            elif kind == "deny":
                keeper._dedupe[record["request_id"]] = _CONFLICT
                keeper._conflicts += 1
            elif kind == "release":
                released.add(record["lease_id"])
                keeper._releases += 1
        now = keeper._now()
        for resource, lease in committed.items():
            if lease.lease_id in released or lease.expires_at <= now:
                if lease.lease_id not in released:
                    keeper._reclaims += 1
                continue
            keeper._install(lease)
        keeper._next_token = max_token + 1
        return keeper

    def grant(self, resource, holder, ttl=30.0, request_id=None):
        """发一份租约；带 request_id 时同一请求的重试返回同一份。

        request_id 复用过但 resource/holder/ttl 对不上，说明是客户端
        把请求标识串用了，抛 ValueError，不发放也不记日志。
        """
        ttl = float(ttl)
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if request_id is not None and not isinstance(request_id, str):
            raise ValueError("request_id must be a string")
        with self._lock:
            now = self._now()
            if request_id is not None:
                cached = self._dedupe.get(request_id)
                if cached is not None:
                    return self._replay(request_id, cached, resource,
                                        holder, ttl)
            old = self._leases.get(resource)
            if old is not None and now < old.expires_at:
                if request_id is not None:
                    self._journal.append(
                        {"event": "deny", "request_id": request_id}
                    )
                    self._dedupe[request_id] = _CONFLICT
                self._conflicts += 1
                raise LeaseConflict(
                    "resource still leased: %r" % (resource,)
                )
            if old is not None:
                self._purge(resource)
                self._reclaims += 1
            token = self._next_token
            lease = Lease(
                lease_id="L%06d" % token,
                resource=resource,
                holder=holder,
                token=token,
                ttl=ttl,
                expires_at=now + ttl,
            )
            self._journal.append(
                {
                    "event": "grant",
                    "request_id": request_id,
                    **_lease_dict(lease),
                }
            )
            self._install(lease)
            self._next_token += 1
            self._grants += 1
            if request_id is not None:
                self._dedupe[request_id] = lease
            self._high[resource] = token
            return lease

    def renew(self, lease_id, holder, ttl=None):
        """续期：纯内存路径，不碰日志、不碰磁盘。

        崩溃恢复后续期仍有效，因为活租约（含原 lease_id）已从日志续
        回；续期本身不落盘，崩在续期后只损失这段延长，按原到期回收。
        """
        if ttl is not None:
            ttl = float(ttl)
            if ttl <= 0:
                raise ValueError("ttl must be positive")
        with self._lock:
            lease = self._find(lease_id)
            if lease is None or lease.holder != holder:
                return None
            now = self._now()
            if now >= lease.expires_at:
                self._purge(lease.resource)
                self._reclaims += 1
                return None
            extend = lease.ttl if ttl is None else ttl
            renewed = replace(lease, ttl=extend, expires_at=now + extend)
            self._wheel.discard(lease.resource, lease.expires_at)
            self._leases[lease.resource] = renewed
            self._wheel.add(lease.resource, renewed.expires_at)
            self._renews += 1
            return renewed

    def release(self, lease_id, holder):
        """提前归还：只有当前持有者能还，先落日志再摘内存。"""
        with self._lock:
            lease = self._find(lease_id)
            if lease is None or lease.holder != holder:
                return False
            self._journal.append({"event": "release", "lease_id": lease_id})
            self._purge(lease.resource)
            self._releases += 1
            return True

    def get(self, resource):
        """资源当前的活租约，没有或已过期返回 None；过期顺手回收。"""
        with self._lock:
            lease = self._leases.get(resource)
            if lease is None:
                return None
            if self._now() >= lease.expires_at:
                self._purge(resource)
                self._reclaims += 1
                return None
            return lease

    def sweep(self):
        """按到期槽清掉过期租约，按资源名排序返回清掉的 Lease。"""
        with self._lock:
            now = self._now()
            resources = self._wheel.pop_due(now)
            dead = []
            for resource in resources:
                lease = self._leases.get(resource)
                if lease is None or now < lease.expires_at:
                    continue
                dead.append(lease)
                self._purge(resource)
            self._reclaims += len(dead)
            return sorted(dead, key=lambda l: l.resource)

    def resources(self):
        """还有活租约的资源名，排序返回；已过期的不算。"""
        with self._lock:
            now = self._now()
            alive = [
                resource
                for resource, lease in self._leases.items()
                if now < lease.expires_at
            ]
            return sorted(alive)

    def stats(self):
        """累计计数，字段口径与内存版 KeeperStats 完全一致。"""
        with self._lock:
            now = self._now()
            active = sum(
                1 for l in self._leases.values() if now < l.expires_at
            )
            return KeeperStats(
                grants=self._grants,
                conflicts=self._conflicts,
                renews=self._renews,
                releases=self._releases,
                reclaims=self._reclaims,
                active=active,
                last_token=self._next_token - 1,
            )

    def high_water(self, resource):
        """resource 的历史最大记号（含崩溃前各纪元），没见过是 0。"""
        with self._lock:
            return self._high.get(resource, 0)

    def seal_guard(self, guard):
        """把全部资源的历史高水位灌进一个 FenceGuard，返回它。

        重启后先灌再放行：guard.check 用新记号通过，旧纪元的旧记号被
        StaleFence 挡在存储层外。
        """
        if not isinstance(guard, FenceGuard):
            raise ValueError("guard must be a FenceGuard")
        with self._lock:
            for resource, token in self._high.items():
                guard.seal(resource, token)
        return guard

    def close(self):
        """关闭底层日志。"""
        self._journal.close()

    @property
    def journal(self):
        """这台租约台挂载的只追加日志，崩溃后拿它去 recover。"""
        return self._journal

    def _replay(self, request_id, cached, resource, holder, ttl):
        if cached is _CONFLICT:
            raise LeaseConflict(
                "request %r was already rejected: %r" % (request_id, resource)
            )
        if (cached.resource, cached.holder, cached.ttl) != (
            resource,
            holder,
            ttl,
        ):
            raise ValueError(
                "request_id %r reused with different grant parameters"
                % (request_id,)
            )
        return cached

    def _install(self, lease):
        """把一份已落日志的租约挂进内存结构（不记数、不动高水位）。"""
        self._leases[lease.resource] = lease
        self._index[lease.lease_id] = lease.resource
        self._wheel.add(lease.resource, lease.expires_at)

    def _purge(self, resource):
        lease = self._leases.pop(resource, None)
        if lease is not None:
            self._index.pop(lease.lease_id, None)
            self._wheel.discard(resource, lease.expires_at)

    def _find(self, lease_id):
        resource = self._index.get(lease_id)
        if resource is None:
            return None
        return self._leases.get(resource)

    def _now(self):
        value = float(self._clock_source())
        if self._now_floor is None or value > self._now_floor:
            self._now_floor = value
        return self._now_floor


def _lease_dict(lease):
    return {
        "lease_id": lease.lease_id,
        "resource": lease.resource,
        "holder": lease.holder,
        "token": lease.token,
        "ttl": lease.ttl,
        "expires_at": lease.expires_at,
    }


def _lease_from(record):
    return Lease(
        lease_id=record["lease_id"],
        resource=record["resource"],
        holder=record["holder"],
        token=record["token"],
        ttl=float(record["ttl"]),
        expires_at=float(record["expires_at"]),
    )
