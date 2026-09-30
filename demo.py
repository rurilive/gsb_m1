"""splay 现状演示。

第一段：用朴素列表实现演示序列的取值、翻转、求和、赋值、最小最大，
看每次操作都在整段上逐元素重排。
第二段：预留的伸展树路径演示位子（见文末注释）。
"""

from splay import Seq


def main():
    print("=== 朴素列表序列（现有能力） ===")
    seq = Seq([5, 3, 8, 1, 9, 2])
    print("  初始        ->", seq.to_list())
    print("  get(2)      ->", seq.get(2))
    seq.reverse(1, 5)
    print("  reverse后   ->", seq.to_list())
    print("  sum(0, 4)   ->", seq.sum(0, 4))
    seq.assign(0, 3, 0)
    print("  assign后    ->", seq.to_list())
    print("  min(0, 6)   ->", seq.min(0, 6))
    print("  max(0, 6)   ->", seq.max(0, 6))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
