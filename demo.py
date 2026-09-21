"""crdtbox 现状演示。

第一段：两个副本各自累加计数器，合并后总值既不重叠也不翻倍。
第二段：集合的加入与移除，以及两个副本合并后的结果。
第三段：ORSet 的删除重入、并发加入胜出、墓碑回收与状态编解码。
"""

import json

from crdtbox.counter import GCounter
from crdtbox.orset import ORSet
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

    print("=== ORSet：删除重入与并发加入胜出 ===")
    p = ORSet("p")
    q = ORSet("q")
    p.add("red")
    q.merge(ORSet.from_dict(p.to_dict()))
    p.discard("red")        # p 删掉 red
    q.add("red")            # q 并发加回 red，没看到 p 的删除
    p.merge(ORSet.from_dict(q.to_dict()))
    q.merge(ORSet.from_dict(p.to_dict()))
    print(f"  并发加入胜出 value={p.value()}")
    p.discard("red").add("red")
    print(f"  删除后可重入 value={p.value()}")

    print("=== ORSet：墓碑回收 ===")
    r = ORSet("r")
    r.merge(ORSet.from_dict(p.to_dict()))
    p.discard("red")
    print(f"  回收前 gc()={p.gc()}（q、r 还没见过这次删除）")
    q.merge(ORSet.from_dict(p.to_dict()))
    r.merge(ORSet.from_dict(p.to_dict()))
    p.merge(ORSet.from_dict(q.to_dict()))
    p.merge(ORSet.from_dict(r.to_dict()))
    print(f"  全网可见后 gc()={p.gc()}")
    print(f"  回收后 contains(red)={p.contains('red')}")

    print("=== ORSet：状态编解码 ===")
    payload = json.dumps(p.to_dict())
    restored = ORSet.from_dict(json.loads(payload))
    print(f"  落盘字节数={len(payload)}")
    print(f"  往返一致={restored.to_dict() == p.to_dict()}")


if __name__ == "__main__":
    main()
