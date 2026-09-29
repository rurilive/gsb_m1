# rankerx

纯标准库的下一个更大元素工具雏形，无外部依赖。

## 现状

rankerx/next.py 提供一个 BruteNext：

- 初始化：用一串整数建起来，bool 不算整数，非整数报 ValueError
- 下标访问与 to_list：按下标取回单个元素，to_list 返回底层数据的一份副本
- next_greater：对某个位置，从它后面挨个往后看，找到第一个比它大的值就返回，
  找不到就用约定值 -1 表示无后继
- next_greater_all：把每个位置的下一个更大元素拼成一个列表返回

next_greater 只有逐个往后找这一条路，区间一长就要把后面每个元素都摸一遍；
还没有下一个更小、前一个更大更小、直方图最大矩形、天数与跨度、滑动窗口最值，
没有单调栈，也没有一次遍历。

## 目标（见任务描述）

在朴素逐个往后找的基础上扩成单调栈系列查询，全部仍放在 rankerx 包里，纯标准库。
约束：

- 现有行为与 tests/test_next.py 基线保持一致（基线一个字不改）
- 新行为另开 tests/test_monotonic.py，用固定序列与逐字断言
- 单调栈只该换掉算的路径，不该改结果：下一个更大等既有结果要与暴力口径逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
