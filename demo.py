"""基线演示：直跑即可看到朴素逐询问重扫的行为与规模痛点。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from morollback import IntervalStats, collapsed_intervals, scan_steps


VALUES = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8]


def first_section():
    stats = IntervalStats(VALUES)
    print("区间不同值个数 3..7 =", stats.query_distinct(3, 7))
    print("区间众数 3..7 =", stats.query_mode(3, 7))
    print("区间最大频率 0..11 =", stats.query_maxfreq(0, 11))
    print("区间内值 5 出现次数 0..11 =", stats.query_count(0, 11, 5))
    print("区间极差 3..7 =", stats.query_range(3, 7))
    print("压平后的区间次序 =", collapsed_intervals([(5, 5), (1, 3), (4, 1)]))
    queries = [(3, 7), (0, 11), (4, 1), (2, 2)]
    print("这批询问的扫描步数 =", scan_steps(VALUES, queries))
    answers, checksum = stats.run(queries)
    print("首个询问的答案 =", answers[0])
    print("总核对值 =", checksum)


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    first_section()
