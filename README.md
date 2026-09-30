# matroid

贪心与拟阵上的最优选择，纯标准库，无外部依赖。

## 现状

`matroid/core.py` 提供一组朴素但正确的枚举实现：

- `Element(label, size, weight, key)`：带权元素，标签非空、容量非负、权为整数
- `Interval(start, end, weight)`、`Task(label, duration, deadline, weight)`：区间与截止期任务
- `is_independent(elements, sub)`：判定 `sub` 是否为独立集
- `max_weight_independent(elements)`：枚举全部子集，取权重最大的独立集
- `max_weight_basis(elements)`：枚举全部子集，取元素个数最多的基
- `max_non_overlapping(intervals)`：枚举全部子区间组合，取个数最多的一组
- `fractional_knapsack(elements, capacity)`：枚举子集后按比值填充，回最优价值与子集
- `integer_knapsack(elements, capacity)`：枚举全部子集，取容量内价值最大的组合
- `max_profit_schedule(tasks)`：枚举全部子集，取能按截止期排完、收益最大的一组

所有对外异常都继承 `Erro`，固定输入重复调用结果一致，不依赖模块级可变状态。

## 问题

只有一层朴素枚举：任何求解都要把全部子集或全部区间组合走一遍，
判定独立性靠对每个子集重扫，区间调度枚举全部子区间组合，
元素一多就是指数级，访问次数与朴素下界差着数量级，也没有可比对的贪心口径。

## 目标

在上面的基础上补出按权排序加增量判定、按结束时间排序、按比值排序、
按端点与截止期排序的贪心路径，并让新老两条路径对同一批数据逐项一致。
见任务描述。约束：

- 现有行为与 `tests/test_core.py` 基线保持一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
