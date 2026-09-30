"""maxrect 改造前基线演示：第一段直跑朴素能力，第二段待实现后补。

直接运行即可看到当前朴素实现在小矩阵上的四条能力与规模计数。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from maxrect.rect import MaxRect, Erro


GRID = [
    [1, 1, 0, 0],
    [1, 0, 0, 1],
    [1, 1, 1, 1],
    [1, 1, 0, 1],
]

WEIGHT = [
    [2, -5, 0, 0],
    [-3, 0, 0, 4],
    [1, 1, 2, 3],
    [1, 1, 0, -2],
]


def first_section():
    """第一段：直接演示改造前的朴素实现（小矩阵）。"""
    matrix = MaxRect(GRID)
    print("规模：%d 行 %d 列" % (matrix.rows, matrix.cols))

    area, rect = matrix.brute_max_rect()
    print("全一子矩形最大面积：%d，位置：%s" % (area, rect))
    print("朴素候选矩形个数：%d" % matrix.rect_visits)
    print("朴素逐格检查次数：%d" % matrix.cell_checks)

    square_area, side = matrix.brute_max_square()
    print("全一子正方形最大面积：%d，最大边长：%d" % (square_area, side))

    best_sum, weight_rect = matrix.brute_max_weight(WEIGHT)
    print("带权最大权值和：%s，位置：%s" % (best_sum, weight_rect))

    heights = matrix.simple_heights()
    print("每格悬线高度：")
    for row in heights:
        print("  " + " ".join(str(value) for value in row))

    indep_area, indep_rect = matrix.independent_suspend()
    print("独立慢速做法面积：%d，位置：%s" % (indep_area, indep_rect))


# TODO: 第二段演示（实现后补）


def main():
    try:
        first_section()
    except Erro as error:
        print("捕获到本包异常：%s" % error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
