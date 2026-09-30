# waveletx

区间查询工具包，纯标准库，无外部依赖。

## 现状

`waveletx/naive.py` 提供朴素区间索引，只有四项能力：

- `kth_smallest(values, lo, hi, k)`：求区间 `[lo, hi)` 内第 `k` 小的元素
- `range_rank(values, lo, hi, value)`：求 `value` 在区间内的排名，即严格小于它的元素个数
- `count_leq(values, lo, hi, value)`：求区间内不超过 `value` 的元素个数
- `count_equal(values, lo, hi, value)`：求 `value` 在区间内出现的次数

区间口径为左闭右开，数组下标从零开始，第 `k` 小的 `k` 同样从零起算。
每项查询都把区间整段取出排序或者逐个扫描，结果正确，但每查一次就线性
甚至平方一次，多次查询就是平方以上量级。`NaiveRangeIndex` 把数组绑定成
索引并累计比较次数，可读取也可清零；非法区间抛 `InvalidRangeError`，
第 `k` 小的 `k` 越界抛 `KthOutOfRangeError`，两者都继承 `WaveletXError`。

它不提供小波树，也没有第二条独立做法可互相印证，更没有把每层访问规模
暴露出来，慢在哪里无从对照。

## 问题

只有一条朴素路径，查询一次就得把区间扫一遍甚至排一遍；区间一长、查询一多，
总代价按平方以上增长；想把查询降到每层访问一次的量级，或者想让两条独立
做法逐项互相印证，都缺入口。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_naive.py` 基线保持一致（基线一个字不改且必须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
