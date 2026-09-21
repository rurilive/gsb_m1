"""addrbook 的扁平地址池。

AddressPool 管一段闭区间的连续 IPv4 地址：allocate 从当前最小
的空闲地址开始发，request 可以点名要某个地址，release 按地址
把地址还回来。池的覆盖范围建好就不变。
"""

from addrbook.address import (
    ADDR_MAX,
    broadcast_of,
    format_addr,
    parse_cidr,
    usable_bounds,
)
from addrbook.errors import (
    AddressInUse,
    AddressNotAllocated,
    OutOfRange,
    PoolExhausted,
)


class AddressPool:
    """一段连续 IPv4 地址的扁平分发器，区间是闭区间 [start, end]。"""

    def __init__(self, start, end):
        if (isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, int) or not isinstance(end, int)):
            raise TypeError("pool bounds must be ints")
        if start < 0 or end > ADDR_MAX or start > end:
            raise OutOfRange("bad pool range: %r..%r" % (start, end))
        self.start = start
        self.end = end
        self._used = set()

    @classmethod
    def from_cidr(cls, text, usable_only=True):
        """按 CIDR 建池。

        usable_only 为真（默认）时按可用地址建池：/30 及更短扣掉
        网络地址与广播地址，/31 和 /32 整段可用；为假则整段全收。
        """
        network, prefix = parse_cidr(text)
        if usable_only:
            first, last = usable_bounds(network, prefix)
        else:
            first, last = network, broadcast_of(network, prefix)
        return cls(first, last)

    def __repr__(self):
        return "AddressPool(%s..%s, used=%d)" % (
            format_addr(self.start), format_addr(self.end), len(self._used))

    @property
    def capacity(self):
        """池里的地址总数。"""
        return self.end - self.start + 1

    @property
    def free(self):
        """还没分配出去的地址个数。"""
        return self.capacity - len(self._used)

    @property
    def in_use(self):
        """已经分配出去的地址个数。"""
        return len(self._used)

    def contains(self, addr):
        """addr 是否落在池的范围内。"""
        return (isinstance(addr, int) and not isinstance(addr, bool)
                and self.start <= addr <= self.end)

    def is_allocated(self, addr):
        """addr 当前是否已经分配。"""
        return addr in self._used

    def allocated(self):
        """已分配地址的升序列表。"""
        return sorted(self._used)

    def allocate(self):
        """分配当前最小的空闲地址，池满了报 PoolExhausted。"""
        for addr in range(self.start, self.end + 1):
            if addr not in self._used:
                self._used.add(addr)
                return addr
        raise PoolExhausted("no free address in %r" % self)

    def request(self, addr):
        """指定地址分配：池外报 OutOfRange，已占用报 AddressInUse。"""
        if not self.contains(addr):
            raise OutOfRange("address outside pool: %r" % (addr,))
        if addr in self._used:
            raise AddressInUse("address already allocated: %s" % format_addr(addr))
        self._used.add(addr)
        return addr

    def release(self, addr):
        """归还地址：池外报 OutOfRange，没分配过报 AddressNotAllocated。"""
        if not self.contains(addr):
            raise OutOfRange("address outside pool: %r" % (addr,))
        if addr not in self._used:
            raise AddressNotAllocated("address not allocated: %s" % format_addr(addr))
        self._used.discard(addr)
