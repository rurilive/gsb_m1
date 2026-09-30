# slopex

划分型动态规划工具集，纯标准库，无外部依赖。

## 现状

`slopex/quadratic.py` 提供一份朴素但正确的实现 `SegmentPlanner`：把序列前
若干项切成若干连续段，用双重循环枚举最后一段的起点求最小总代价。重量为段
内各元素之和，长度为段内元素个数，起点为段的起始下标。

- `SegmentPlanner(policy, coef)`：构造时校验策略名与每段固定开销
- `segment_cost(weight, length, start)`：单段代价，`square` 取重量平方加开销，
  `position` 取重量乘起点下标加一再加开销
- `best_partition(seq)`：最优划分的最小总代价，空序列返回 0
- `best_partitions(seq)`：每个前缀的最优代价序列，长度为项数加一
- `best_cut_points(seq)`：取到最优划分时的各段切点列表，并列取起点最小者
- `compare_count(n)`：平方枚举在规模为 n 时的转移比较次数，等于 n 乘 n 加一
  的一半

异常统一挂在 `slopex.quadratic.SlopexError` 之下（也可从包根 `slopex` 导入）：
`InvalidPolicyError`、`InvalidWeightError`、`InvalidSequenceError`。

## 问题

转移里枚举最后一段的起点是双重循环，每加一个前缀都要把前面所有起点重看一遍，
比较次数长成规模的平方。序列长时重复劳动成倍放大，始终停在朴素口径上，没有
把转移式整理成直线形式、用下凸壳维护候选、用单调指针均摊取最优这些做法。

## 目标

见任务描述。约束：

- `tests/test_planner.py` 是基线，一字不许改且必须全绿
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
