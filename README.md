# jobdag

任务依赖图调度底座，纯标准库，无外部依赖。内部补数链路和离线对账都挂在它上面。

## 包结构

- `jobdag/graph.py`：`JobGraph` 声明节点和依赖，`topo_order()` 压出执行序；
错误类型 `DuplicateJobError` / `UnknownDepError` / `CycleError`
- `jobdag/runner.py`：`SequentialRunner` 按执行序单线程跑，失败即中断
- `jobdag/report.py`：`RunReport` 记逐节点终态、返回值、异常和耗时
- `jobdag/scheduler.py`：`Scheduler(graph, max_parallel)` 多线程并发跑，
  失败/超时只跳过下游，支持重试、超时和跨线程 `cancel()`

## 用法

```python
from jobdag import JobGraph, SequentialRunner

graph = JobGraph()
graph.add("scan", scan_fn)
graph.add("merge", merge_fn, deps=["scan"])

report = SequentialRunner().run(graph)
print(report.status("merge"), report.results.get("merge"))
```

依赖可以先引用后声明。并发调度在 `add` 上配重试与超时：

```python
from jobdag import Scheduler

graph.add("flaky", flaky_fn, retries=2, timeout=5.0)
scheduler = Scheduler(graph, max_parallel=8)
report = scheduler.run()
```

- 终态：`ok` / `failed` / `timeout` / `skipped` / `cancelled`；失败或超时
  节点的下游记 `skipped`，无关分支照跑，`run()` 始终返回报告而不是抛异常
- `report.attempts` 是每个节点的实际尝试次数（skipped/cancelled 记 0）
- `cancel()` 可由任意线程在 `run()` 前后调用：没开工的节点记 `cancelled`，
  在跑的节点跑完照记；`run()` 返回后报告不再变化
- `max_parallel=1` 时执行序与 `SequentialRunner` 一致
- `CycleError.nodes` 列出环上节点，错误信息形如 `a -> b -> c -> a`

## 运行

```bash
python3 demo.py                           # 顺序跑一张演示图
python3 -m unittest discover -s tests -v  # 行为基线
```
