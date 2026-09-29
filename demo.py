"""OrderedMap 现状演示。

第一段：插入、按 key 查找、范围扫描。
第二段：预留的跳表演示位子（见文末注释）。
"""

from skiplist.ordered import OrderedMap


def main():
    print("=== 有序映射 ===")
    m = OrderedMap()
    for k in (5, 1, 4, 2, 3):
        m.put(k, k * k)
    print(f"  keys   = {m.keys()}")
    print(f"  get(4) = {m.get(4)}")
    print(f"  get(9) = {m.get(9)}")
    print(f"  range_scan(2, 4) = {m.range_scan(2, 4)}")
    print(f"  first  = {m.first()}")

    # TODO(跳表改造): 跳表实现后，在这里加一段演示：
    # 注入 seed 复现层级分布、按 key 删除与层级收缩、rank(k)、range 有序返回。


if __name__ == "__main__":
    main()
