"""SortedList 现状演示。

第一段：插入若干键值，再按序遍历读取。
第二段：预留的 B 树演示位子（见文末注释）。
"""

from btreelab.index import SortedList


def main():
    print("=== 有序列表 ===")
    m = SortedList()
    for k in (5, 1, 4, 2, 3):
        m.put(k, k * k)
    print(f"  keys   = {m.keys()}")
    print(f"  get(4) = {m.get(4)}")
    print(f"  get(9) = {m.get(9)}")
    print(f"  range_query(2, 4) = {m.range_query(2, 4)}")
    print(f"  first  = {m.first()}")

    # TODO(B 树改造): B 树实现后，在这里加一段演示：
    # 补一轮插入触发分裂、按区间范围查询、按序遍历全部键值。


if __name__ == "__main__":
    main()
