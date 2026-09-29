"""connpool 现状演示。

第一段：借出复用——两条连接轮流借还，看池内复用与计数。
第二段：预留的借还上限、超时借出与事务绑定演示位子（见文末注释）。
"""

from connpool import ConnectionPool


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

    # TODO(借还上限、超时与事务绑定): 上限等待队列、带超时的 acquire、溢出连接、
    # 健康检查与重建、事务绑定与泄漏报告都补齐后，在这里加一段演示：
    # 用一个假时钟逼出 acquire(timeout=...) 的超时异常；
    # 借满上限后再借，打印它进入等待队列而不是无限新建；
    # 开一个事务，打印事务未提交前连接不归还池中，提交后才回到空闲。


if __name__ == "__main__":
    main()
