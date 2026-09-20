"""bufpool 现状演示：朴素分配器的取用、计数与在借视图。

第二段是留给池化演示的位子，见文末注释。
"""

from bufpool import Allocator, OVERSIZE, tier_of


def show_tier(size):
    tier = tier_of(size)
    return str(tier) if tier is not None else OVERSIZE


def main():
    clock = [1000.0]

    def now():
        return clock[0]

    alloc = Allocator(clock=now)

    print("=== 取用与计费 ===")
    buffers = []
    for size in (200, 3000, 70000):
        buf = alloc.acquire(size)
        buf.view()[:4] = b"ping"
        buffers.append(buf)
        print("  size=%-6d capacity=%-6d 档位=%s" % (buf.size, buf.capacity,
                                                    show_tier(size)))
        clock[0] += 0.4

    print("=== 在借视图 ===")
    for serial, size, age in alloc.outstanding():
        print("  #%d size=%-6d 已持有 %.1f 秒" % (serial, size, age))

    print("=== 归还与计数 ===")
    for buf in buffers:
        alloc.release(buf)
    snap = alloc.stats()
    print("  acquisitions=%d releases=%d live=%d peak=%d bytes=%d" % (
        snap["acquisitions"], snap["releases"], snap["live"],
        snap["peak_live"], snap["bytes_acquired"]))
    print("  档位分布 %s" % snap["tier_counts"])

    # TODO(池化): PooledAllocator 落地后，在这里补第二段演示：
    # 同样几档容量反复 acquire/release，看命中与复用计数、
    # 空闲超时后 sweep 把内存还掉、以及借了不还超时被 leak_report 报出来。


if __name__ == "__main__":
    main()
