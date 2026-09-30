# spanx

序列左右边界的朴素工具箱，纯标准库，无外部依赖。

## 现状

spanx/spans.py 提供一组最直白的实现，全部用双向扫描或逐位置外扩：

- first_greater_left / first_greater_right / first_smaller_left / first_smaller_right：
  对某个位置，从它出发向左或向右一格一格地看，谁先满足严格更大或严格更小就返回谁，
  一直没有就返回约定值 -1
- greater_bounds / smaller_bounds：把每个位置左右两侧第一个更大或更小的下标各拼成列表
- min_range_lengths：以每个元素为最小值的最大区间长度，向两侧扩到严格更小处
- daily_temperatures：每日温度，向右看第一个严格更暖的天与它相隔多少天
- histogram_bounds：柱状图每根柱子向左向右能扩到的第一家更矮柱子的下标
- largest_rectangle：柱状图最大矩形面积，逐位置把它当作最矮的那一根再向两侧扩
- count_naive_visits：统计做一轮左右更大边界查询总共比较多少次
- SpanError / EmptyInputError / InvalidInputError：异常统一派生自 SpanError
- 非整数、bool 冒充整数、越界下标一律在入口抛 InvalidInputError；查空序列抛 EmptyInputError

## 问题

每个位置都靠向左向右各扫一遍定边界，序列一长就退到平方量级：一次全量查询要做的
比较次数随长度近似平方增长。既没有单调栈，也没有一次遍历；四类边界、每日温度、
以最小值为界的最大区间、柱状图边界与最大矩形，全是逐位置在内层反复外扩，一段长
序列上反复白扫。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_spans.py 基线一致（基线一个字不改，且必须全绿）
- 新行为另开 tests/test_sparse.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
