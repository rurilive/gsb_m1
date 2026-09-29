"""BorrowPool 现状演示。

第一段：借一个还一个再借同一个，看最朴素池的复用与新建计数。
第二段：预留的分档借还与复用演示位子（见文末注释）。
"""

from slabbin.pool import BorrowPool


def main():
    print("=== 朴素借还池 ===")
    pool = BorrowPool()
    a = pool.borrow()
    print(f"  borrow() -> {a!r}，created={pool.created}")
    pool.give_back(a)
    again = pool.borrow()
    print(f"  归还 a 后再借 -> {again!r}，复用={again is a}，created={pool.created}")
    pool.give_back(again)
    print(f"  空闲 idle={pool.idle}")

    # TODO(内存池改造): 在 slabbin 里实现带尺寸分档、空闲复用、每档容量上限与淘汰、
    # 生命周期校验、统计与边界 fail fast 的内存池分配器后，在这里加一段演示：
    # 一轮按大小分档借出与归还、归还块回到所属档并在同档请求里被复用、超限归还被丢弃，
    # 以及统计里各档空闲数、借出数、复用命中率与新建次数随操作序列的变化。


if __name__ == "__main__":
    main()
