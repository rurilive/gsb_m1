"""votehal: 众数与多数投票统计工具的朴素实现。

当前只有一条路：求多数元素时对每个候选把整条序列从头再扫一遍数出现
次数，求超过元素种类数分之一的众数时枚举全部候选逐个重扫，求前几频
繁元素靠全排序。见 votehal/naive.py，线性做法见任务描述。
"""

from votehal.naive import (
    Erro,
    VoteError,
    VoteTools,
    count_value,
    frequent_values,
    has_majority,
    majority_count,
    majority_value,
    naive_counts,
    top_frequent,
    two_pass_majority,
    visit_count,
)

__all__ = [
    "Erro",
    "VoteError",
    "VoteTools",
    "count_value",
    "frequent_values",
    "has_majority",
    "majority_count",
    "majority_value",
    "naive_counts",
    "top_frequent",
    "two_pass_majority",
    "visit_count",
]
