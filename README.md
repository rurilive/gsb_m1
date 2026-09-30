# ivsched

区间调度与区间集合统计的朴素实现雏形，纯标准库，无外部依赖。

## 现状

`ivsched/core.py` 提供 `NaiveIntervalScheduler`，只有一条最直白的路：核心类持有一批
闭区间，求最大不相交区间数与带权最大权值不相交集时，把区间下标的全集枚举成一个个
子集，再对每个子集逐对判断是否重叠，留下两两不重叠的子集里最大最重的那一批，具体
选中的区间下标按写死的字典序口径给出。

- `add(start, end, weight=1)`、`size()`、`intervals()`、`interval(index)`：登记区间与读取
- `overlaps(a, b)`：两个闭区间是否有公共点，端点相等算重叠
- `all_disjoint_selections()`：全部两两不重叠的子集，按升序下标元组给出（含空集）
- `max_disjoint_count()`：最大不相交区间数
- `max_weighted_value()`：带权最大权值不相交集的总权值
- `best_disjoint_selection()`、`best_weighted_selection()`：最大或最重的那一批下标
- `count_subsets()`、`count_overlap_checks()`、`count_weight_sums()`、`cost_report()`：
  枚举子集、重叠判定与求和次数的规模计数

现状全部走穷举口径：子集总数为 2 的区间数次方，逐个子集逐对判定重叠。口径直白、
结果确定，但区间一多，枚举量就随区间数指数级上涨。异常基类是 `Erro`，端点非法抛
`BadInterval`，权值非法抛 `BadWeight`，区间下标越界抛 `UnknownInterval`。

## 问题

没有按右端点排序的贪心与加权区间调度的动态规划，最大不相交与带权最大权值拿不到
排序为主的代价；区间点覆盖最少点数、区间合并输出互不相交并集这两个能力也没有独立
的路，更读不到穷举口径与排序口径的规模对照。

## 目标

见任务描述。约束：

- `tests/test_baseline.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件，基线路径不许删除
- 纯标准库，不引第三方

## 运行

```bash
python3 demo.py                          # 穷举全部子集演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
