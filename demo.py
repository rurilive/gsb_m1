"""treap 现状演示。

第一段：用朴素列表实现演示序列的取值、按位置插入删除、区间求和、
区间最小最大、区间第 k 小与按排名找元素，看每次操作都在整段上
逐元素重排或重新扫描。
第二段：预留的无旋树路径演示位子（见文末注释）。
"""

from treap import Seq


def main():
    print("=== 朴素列表序列（现有能力） ===")
    seq = Seq([5, 3, 8, 1, 9, 2])
    print("  初始        ->", seq.to_list())
    print("  get(2)      ->", seq.get(2))
    seq.insert(1, 7)
    print("  insert后    ->", seq.to_list())
    seq.remove(4)
    print("  remove后    ->", seq.to_list())
    print("  sum(0, 4)   ->", seq.sum(0, 4))
    print("  min(0, 4)   ->", seq.min(0, 4))
    print("  max(0, 4)   ->", seq.max(0, 4))
    print("  kth(0,4,1)  ->", seq.kth(0, 4, 1))
    print("  rank(0)     ->", seq.rank(0))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
