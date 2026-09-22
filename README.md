# jqplan

数据平台的小查询引擎，纯标准库，多表等值连接全在内存里跑。

## 结构

- `jqplan/table.py` 的 `Table`：行是值元组，`insert` / `insert_many` / `rows` /
  `row_count` / `distinct`，每次写入推进 `revision`
- `jqplan/engine.py` 的 `Query` / `Plan` / `Engine`：`Query` 声明参与的表、等值条件
  （表名对，列名对）和输出列；`Engine.execute` 按声明顺序执行，
  `Engine.execute_plan` 按计划给的顺序执行，两者都返回 `ExecutionResult`，
  里面有 `rows`、`rows_scanned`（探测行数）和 `order`
- `jqplan/stats.py` 的 `Stats`：`Stats.collect(tables)` 扫一遍表，得到行数、各列基数
  和采集时的 `revision`；`stale(tables)` 列出对不上的表名
- `jqplan/planner.py` 的 `Planner`：`plan(query, stats=None)` 现在直接返回声明顺序

输出列的顺序跟着查询声明走，跟执行顺序无关；条件在涉及的两张表都进入前缀之后
立刻参与过滤。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py                           # 执行顺序与探测行数演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

## 连接顺序规划

`Planner.plan(query, stats)` 拿到统计快照后按估计代价重排连接顺序，
`stats` 传 `None` 时仍返回声明顺序：

- 代价模型：用行数和连接列基数估计每个前缀的中间结果大小
  （各表行数相乘，每条等值条件除以两侧基数的较大者），再按嵌套循环的
  口径累加估计探测行数，跟 `Engine` 实际执行的 `rows_scanned` 同一个公式
- 组内不超过 12 张表时用子集动态规划求估价最优，更大的组换贪心
  （每步选让中间结果最小的表），十一张表规划耗时在毫秒级
- `Planner.components(query)` 按等值条件把表分成连通组，组内各自排好，
  组与组之间按叉乘代价（相邻交换准则）排序后拼接
- 统计缺表、过期（`revision` 对不上）或缺连接列基数时，整体退回声明顺序
- 同样的查询加同样的统计必得同一个计划；`Engine` 的执行方式和探测行数
  口径不变
