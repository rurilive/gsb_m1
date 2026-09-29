"""meldset 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from meldset.merge import HeapMerge


def baseline_demo():
    hm = HeapMerge()
    a = hm.make_set([1, 2, 3])
    b = hm.make_set([3, 4, 5])
    hm.set_attr(a, 1, "color", "red")

    print("a 大小:", hm.size_of(a))
    print("b 大小:", hm.size_of(b))

    merged = hm.union_sets(a, b)
    print("合并后大小:", hm.size_of(merged))
    print("元素 1 的属性:", hm.query(merged, 1))
    print("元素 4 的属性:", hm.query(merged, 4))


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：小并大合并、搬迁计数与属性维护 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
