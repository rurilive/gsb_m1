"""基线演示：直跑即可看到朴素逐点查询的行为与规模痛点。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from treemo import PathQuerier, step_count


#          0
#        / | \
#       1  2  3
#      / \    | \
#     4   5   6  7
PARENTS = [-1, 0, 0, 0, 1, 1, 3, 3]
WEIGHTS = [3, 1, 4, 5, 2, 7, -1, 6]


def first_section():
    q = PathQuerier(8, PARENTS, WEIGHTS)
    print("路径不同权值个数 4->7 =", q.path_distinct(4, 7))
    print("路径权值和 4->7 =", q.path_sum(4, 7))
    print("路径最大值 6->5 =", q.path_max(6, 5))
    print("路径上权值 5 出现次数 4->7 =", q.path_count(4, 7, 5))
    print("路径上最多的权值 4->7 =", q.path_mode(4, 7))
    print("逐级步数 4->7 =", q.walk_steps(4, 7))
    print("一次路径查询步数 4->7 =", step_count(q, 4, 7))
    results, checksum = q.run([(4, 7, 5), (2, 2, 4), (0, 7, -1)])
    print("一批查询首条结果 =", results[0])
    print("总核对值 =", checksum)


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    first_section()
