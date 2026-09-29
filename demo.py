"""ConnectionPool 现状演示。

第一段：借出复用——两条连接轮流借还，看池内复用与计数。
第二段：预留的时限借出与健康剔除演示位子（见文末注释）。
"""

from poolnex.pool import ConnectionPool


def main():
    print("=== 借出与复用（上限 2） ===")
    pool = ConnectionPool(2)
    a = pool.acquire()
    b = pool.acquire()
    print(f"  acquire() -> {a!r} {b!r}")
    pool.release(a)
    again = pool.acquire()
    print(f"  归还 a 后再借 -> {again!r}，复用={again is a}")
    pool.release(b)
    pool.release(again)
    s = pool.stats()
    print(f"  stats: active={s['active']} idle={s['idle']} created={s['created']}")

    # TODO(时限借出与健康剔除): 超时借出、坏连接剔除、空闲过期与关闭语义实现后，
    # 在这里加一段演示：注入假时钟让 acquire(timeout=...) 到期抛超时、
    # 标记某连接不健康后借出时被剔除并重建，以及 close() 之后借出的拒绝语义。


if __name__ == "__main__":
    main()