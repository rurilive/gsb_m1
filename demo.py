"""addrbook 现状演示：一个 /29 动态池的分配、指定申请与归还。

跑法：python3 demo.py
"""

from addrbook import AddressPool, PoolExhausted, format_addr, parse_addr


def main():
    pool = AddressPool.from_cidr("10.0.0.0/29")
    print("池范围 %s 到 %s，可用 %d 个（/29 扣掉了网络与广播地址）" % (
        format_addr(pool.start), format_addr(pool.end), pool.capacity))

    print("=== 逐个分配，从最小空闲地址开始 ===")
    handed = [pool.allocate() for _ in range(3)]
    for addr in handed:
        print("  分配 %s" % format_addr(addr))
    print("  在用 %d，空闲 %d" % (pool.in_use, pool.free))

    print("=== 点名申请一个固定地址 ===")
    fixed = pool.request(parse_addr("10.0.0.5"))
    print("  申请 %s，在用 %d" % (format_addr(fixed), pool.in_use))

    print("=== 归还最小地址，再分配会优先拿回它 ===")
    pool.release(handed[0])
    print("  归还 %s" % format_addr(handed[0]))
    print("  再分配得到 %s" % format_addr(pool.allocate()))

    print("=== 写满这个池 ===")
    while True:
        try:
            pool.allocate()
        except PoolExhausted:
            print("  池已用尽，在用 %d，空闲 %d" % (pool.in_use, pool.free))
            break
    print("  已分配：%s" % ", ".join(format_addr(x) for x in pool.allocated()))


if __name__ == "__main__":
    main()
