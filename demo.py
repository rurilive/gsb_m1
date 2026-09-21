"""crdtbox 现状演示。

第一段：两个副本各自累加计数器，合并后总值既不重叠也不翻倍。
第二段：集合的加入与移除，以及两个副本合并后的结果。
第三段：预留的因果合并与编解码演示位子（见文末注释）。
"""

from crdtbox.counter import GCounter
from crdtbox.set import TwoPhaseSet


def main():
    print("=== 计数器：两副本合并 ===")
    a = GCounter("a")
    b = GCounter("b")
    a.incr("a", 3)
    b.incr("b", 4)
    print(f"  合并前 a={a.value()} b={b.value()}")
    a.merge(b)
    b.merge(a)
    print(f"  合并后 a={a.value()} b={b.value()}")

    print("=== 集合：加入与移除 ===")
    x = TwoPhaseSet()
    y = TwoPhaseSet()
    x.add("red").add("blue")
    y.add("green")
    y.merge(x)
    y.discard("red")
    x.merge(y)
    print(f"  value={x.value()}")
    print(f"  contains(red)={x.contains('red')}")

    # TODO(因果合并改造): 删除重入、并发加入胜出、墓碑回收、
    # 状态编解码的演示都加在这一段下面。


if __name__ == "__main__":
    main()
