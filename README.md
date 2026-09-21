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
