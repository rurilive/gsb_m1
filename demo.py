"""chunkheap 现状演示。

第一段：用最朴素的一进一出分配器连续分配两块，看偏移怎么往后推，
释放之后再看分配器并没有回收任何空间。
第二段：预留的空闲链复用与碎片整理演示位子（见文末注释）。
"""

from chunkheap.alloc import BumpAlloc


def main():
    print("=== 朴素一进一出分配器 ===")
    heap = BumpAlloc(256)
    first = heap.alloc(32)
    second = heap.alloc(16)
    print(f"  alloc(32) -> {first}，alloc(16) -> {second}")
    print(f"  两块起始偏移差 = {second - first}（头部 {BumpAlloc.HEADER} 加 32）")
    print(f"  已用 {heap.used} / 容量 {heap.capacity}")

    heap.free(first)
    after = heap.alloc(16)
    print(f"  释放 {first} 后再 alloc(16) -> {after}，复用了旧块吗：{after == first}")
    print(f"  释放后已用 {heap.used}，容量只减不增")

    # TODO(空闲链与碎片整理改造): 在 chunkheap 里实现带空闲链、最佳适配复用、
    # 相邻空闲块合并、按对齐边界分配、大块直通与碎片统计的分配器后，在这里加一段演示：
    # 一轮分配与释放之后，释放出来的块进入空闲链，再次分配时被复用拿到原来的偏移；
    # 两侧相邻块都释放后合并成一个更大的空闲块，最大空闲块随之变大，外部碎片度量下降；
    # 最后打印在用块数、空闲块数、最大空闲块与碎片度量，并对比容量为零、超容量分配、
    # 重复释放等边界情形的报错。


if __name__ == "__main__":
    main()
