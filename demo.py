"""segtree 演示脚本，直接 `python3 demo.py` 即可运行。

第一段跑改造前的基线功能（逐项区间数组）。
第二段是留给改造后的占位，实现完再补。
"""

from segtree.range import RangeArray


def demo_baseline():
    print("== 第一段：改造前基线（逐项区间数组） ==")
    a = RangeArray([0, 0, 0, 0, 0, 0])
    print("初始:      ", a.to_list())
    a.range_add(1, 4, 5)
    print("区间加后:  ", a.to_list())
    print("区间和[1,4):", a.range_sum(1, 4))
    print("区间最值[1,4):", a.range_max(1, 4))
    a.set(0, 42)
    print("单点设值后:", a.to_list())
    print("长度:      ", len(a))


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    demo_baseline()
