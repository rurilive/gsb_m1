"""matchingx 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from matchingx.pair import BrutePair


def baseline_demo():
    bp = BrutePair()
    bp.add_edge("l1", "r1")
    bp.add_edge("l1", "r2")
    bp.add_edge("l2", "r1")
    bp.add_edge("l3", "r2")

    print("左侧点:", sorted(bp.left_points))
    print("右侧点:", sorted(bp.right_points))
    print("边数:", bp.edge_count())
    print("最大匹配条数:", bp.max_pairs())
    print("是否存在完美匹配:", bp.is_perfect())
    print("l1 配到:", bp.matched_to("l1"))


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：增广路匹配、最小点覆盖与最大独立集 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
