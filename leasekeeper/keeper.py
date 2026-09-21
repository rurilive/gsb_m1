"""单机租约发放台：一个资源同时至多一份活租约，过期按注入钟惰性判定。

调度平台的节点从这里领租约去抢资源：grant 发新份并给出只增记号，renew
续期，release 提前归还，sweep 清扫过期。过期一律按注入的单调时钟算时
长，绝不去看墙上时间。纯标准库，clock 注入方便测试拨时间。
"""

import threading
import time
from dataclasses import dataclass, replace


class LeaseConflict(Exception):
    """资源上还有未过期的租约，这次发放被拒。"""


@dataclass(frozen=True)
class Lease:
    """一份租约：id、资源、持有者、只增记号、租期与到期时刻。"""

    lease_id: str
    resource: str
    holder: str
    token: int
    ttl: float
    expires_at: float


@dataclass(frozen=True)
class KeeperStats:
    """累计操作计数与当前状态。"""

    grants: int
    conflicts: int
    renews: int
    releases: int
    reclaims: int
    active: int
    last_token: int


class LeaseKeeper:
    """按资源发租约的单机实现。

    clock: 返回当前单调时刻的可调用对象，默认 time.monotonic，测试可
    注入假时钟精确拨进拨出。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._leases = {}      # resource -> 租约（含已过期还没被清的）
        self._next_token = 1
        self._grants = 0
        self._conflicts = 0
        self._renews = 0
        self._releases = 0
        self._reclaims = 0

    def grant(self, resource, holder, ttl=30.0):
        """给 resource 发一份 ttl 秒的租约给 holder，返回 Lease。

        资源上还有活租约时抛 LeaseConflict。记号从 1 起按发放次序递增；
        发现过期旧租约顺手清掉，计入回收。到期那一刻起就算过期。
        """
        ttl = float(ttl)
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        with self._lock:
            now = self._clock()
            old = self._leases.get(resource)
            if old is not None:
                if now < old.expires_at:
                    self._conflicts += 1
                    raise LeaseConflict(
                        "resource still leased: %r" % (resource,)
                    )
                del self._leases[resource]
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
            self._leases[resource] = lease
            self._grants += 1
            return lease

    def renew(self, lease_id, holder, ttl=None):
        """把 lease_id 续到当前时刻加租期，返回续后的 Lease，失败 None。

        只认 id 加持有者：不存在、已过期或人不对都算失败。ttl 不传沿用
        原租期，传了就用新值并把这份租约的租期一并换掉。
        """
        if ttl is not None:
            ttl = float(ttl)
            if ttl <= 0:
                raise ValueError("ttl must be positive")
        with self._lock:
            lease = self._find(lease_id)
            if lease is None or lease.holder != holder:
                return None
            now = self._clock()
            if now >= lease.expires_at:
                del self._leases[lease.resource]
                self._reclaims += 1
                return None
            extend = lease.ttl if ttl is None else ttl
            renewed = replace(lease, ttl=extend, expires_at=now + extend)
            self._leases[lease.resource] = renewed
            self._renews += 1
            return renewed

    def release(self, lease_id, holder):
        """提前归还租约，只有当前持有者能还；成功 True，否则 False。"""
        with self._lock:
            lease = self._find(lease_id)
            if lease is None or lease.holder != holder:
                return False
            del self._leases[lease.resource]
            self._releases += 1
            return True

    def get(self, resource):
        """资源当前的活租约，没有或已过期返回 None；过期顺手清掉。"""
        with self._lock:
            lease = self._leases.get(resource)
            if lease is None:
                return None
            if self._clock() >= lease.expires_at:
                del self._leases[resource]
                self._reclaims += 1
                return None
            return lease

    def sweep(self):
        """清掉所有已过期租约，按资源名排序返回清掉的 Lease 列表。"""
        with self._lock:
            now = self._clock()
            dead = [l for l in self._leases.values() if now >= l.expires_at]
            for lease in dead:
                del self._leases[lease.resource]
            self._reclaims += len(dead)
            return sorted(dead, key=lambda l: l.resource)

    def resources(self):
        """还有活租约的资源名，排序返回；已过期的不算。"""
        with self._lock:
            now = self._clock()
            return sorted(
                r for r, l in self._leases.items() if now < l.expires_at
            )

    def stats(self):
        """累计计数：发放、冲突、续期、归还、回收、活跃数与最后记号。"""
        with self._lock:
            now = self._clock()
            active = sum(1 for l in self._leases.values() if now < l.expires_at)
            return KeeperStats(
                grants=self._grants,
                conflicts=self._conflicts,
                renews=self._renews,
                releases=self._releases,
                reclaims=self._reclaims,
                active=active,
                last_token=self._next_token - 1,
            )

    def _find(self, lease_id):
        for lease in self._leases.values():
            if lease.lease_id == lease_id:
                return lease
        return None
