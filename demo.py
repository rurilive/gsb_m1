"""Small demo for the rankly package.

The first block exercises the current baseline (sort-based Top-K).  The second
block is a placeholder for the streaming/heap work described in the task.
"""

from rankly import SortTopK


def baseline_demo():
    data = [12, 5, 27, 3, 19, 8, 41]
    tool = SortTopK(data, k=3)
    print("baseline top 3:", tool.top())


# TODO(堆与流式改造): 补充一轮流式 Top-K 与中位数演示。


if __name__ == "__main__":
    baseline_demo()
