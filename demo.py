"""crdtbox 现状演示。

第一段：两个副本各自累加计数器，合并后总值既不重叠也不翻倍。
第二段：集合的加入与移除，以及两个副本合并后的结果。
第三段：预留的因果合并与编解码演示位子（见文末注释）。
"""

from crdtbox.counter import GCounter
from crdtbox.set import TwoPhaseSet
from crdtbox.aworset import AWORSet


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

    print("=== 因果集合：删除重入与并发加入胜出 ===")
    p = AWORSet("p")
    q = AWORSet("q")
    p.add("red").add("blue")
    q.merge(p)
    q.discard("red")   # q 删掉 red
    p.add("red")       # p 并发地把 red 加回来
    p.merge(q)
    q.merge(p)
    print(f"  合并后 p={p.value()} q={q.value()}")
    print(f"  并发加入胜出 contains(red)={p.contains('red')}")
    q.discard("red")   # 删除生效后还能再加回来
    p.merge(q)
    print(f"  再次删除 p={p.value()}")
    p.add("red")
    q.merge(p)
    print(f"  删除后重入 q={q.value()}")

    print("=== 墓碑回收 ===")
    print(f"  全状态同步下墓碑数={p.tombstone_count()}（删除已被因果时钟吸收）")

    print("=== 状态编解码 ===")
    payload = p.dumps()
    r = AWORSet.loads(payload)
    print(f"  编码 {len(payload)} 字节，解码后 value={r.value()}")
    print(f"  往返一致={r.to_dict() == p.to_dict()}")


if __name__ == "__main__":
    main()
