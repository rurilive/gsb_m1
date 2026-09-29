"""gclab 现状演示。

第一段：引用计数——分配对象、建立引用、解除引用，看计数归零当场回收。
第二段：预留的标记清扫与分代演示位子（见文末注释）。
"""

from gclab import GCError, RefCountHeap


def main():
    print("=== 引用计数堆（计数归零立即回收） ===")
    heap = RefCountHeap()
    a = heap.alloc("root")
    b = heap.alloc("child")
    c = heap.alloc("leaf")
    heap.add_root(a)
    heap.add_ref(a, b)
    heap.add_ref(b, c)
    print(f"  存活对象：{heap.objects()}")
    print(f"  b 的计数：{heap.ref_count(b)}")
    print(f"  解除 a 对 b 的引用后存活对象：", end=" ")
    heap.remove_ref(a, b)
    print(f"{heap.objects()}")
    print(f"  累计回收：{heap.collected()}")

    print("  环无法回收：")
    x = heap.alloc("x")
    y = heap.alloc("y")
    heap.add_root(x)
    heap.add_root(y)
    heap.add_ref(x, y)
    heap.add_ref(y, x)
    heap.remove_root(x)
    heap.remove_root(y)
    print(f"  存活对象仍含有环：{heap.objects()}，累计回收：{heap.collected()}")

    try:
        heap.payload(999)
    except GCError as exc:
        print(f"  未知对象 -> {exc.__class__.__name__}")

    # TODO(标记清扫改造): 换成一个标记清扫垃圾回收器后，在这里加一段演示：
    # 用根集合跑一轮标记清扫，打印回收前后的存活集合与回收计数，
    # 展示环内无外部引用时整环被回收；
    # 再触发一次新代回收并让对象提升到老代，打印提升后的存活对象。


if __name__ == "__main__":
    main()
