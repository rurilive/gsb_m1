# intervalx

区间集合工具包，纯标准库，无外部依赖。

## 现状

intervalx/interval.py 提供 IntervalSet：

- IntervalSet(intervals=())：以二元组列表为底座，每个区间是（左端，右端），
  两端是非布尔整数且左端不大于右端，否则在构造时拒绝
- merge()：反复在两两之间比较，把可连通的区间并成一段，直到不再变化
- intersection()：逐对区间求交，再把结果合并去重
- coverage_length() / union_length()：取全部端点，对每段逐点逐区间判定是否被覆盖
- covers_point(point) / coverage_count(point) / is_covered(point)：逐点逐区间判定
- max_overlap()：遍历全部整点，对每个点逐个数覆盖它的区间
- contains_pair(i, j) / containment()：四次端点比较求包含关系
- cover_with(target)：贪心最少覆盖，返还下标序列，并列时取下标较小者
- independent_brute_merge() / independent_brute_max_overlap()：两条独立慢速做法
- comparison_count() / access_count()：朴素两两比较次数与逐点访问次数，
  扫描线路径基线恒为零

内部所有能力都是两两比较或逐点逐区间判定，区间一多就慢，但结果正确。

## 问题

求合并结果时反复扫描每一对区间，比较次数随区间数平方增长；求交集把区间两两配对；
覆盖长度与最大重叠数按整点逐个去数，点坐标范围一大就慢；包含关系也是两两比对；
最少覆盖每一步把所有区间扫一遍。既没有按左端点排序后用扫描线一趟推进的手段，
也拿不出任何计数说明更聪明的做法省了多少，升级路径与朴素路径之间没有逐项核验。
空区间集合、单区间、区间退化为一点、端点相同、完全包含、完全不重叠、全部重叠、
重复区间、端点含负值、目标区间无法覆盖这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_interval.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
