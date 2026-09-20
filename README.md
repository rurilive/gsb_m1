# jobdag

任务依赖图调度底座，纯标准库，无外部依赖。内部补数链路和离线对账都挂在它上面。

## 包结构

- `jobdag/graph.py`：`JobGraph` 声明节点和依赖，`topo_order()` 压出执行序；
  错误类型 `DuplicateJobError` / `UnknownDepError` / `CycleError`
- `jobdag/runner.py`：`SequentialRunner` 按执行序单线程跑，失败即中断
- `jobdag/scheduler.py`：`Scheduler` 线程池真并行调度，支持重试、超时与撤销
- `jobdag/report.py`：`RunReport` 记逐节点终态、返回值、异常、耗时和尝试次数

## 用法

```python
from jobdag import JobGraph, SequentialRunner

graph = JobGraph()
graph.add("scan", scan_fn)
graph.add("merge", merge_fn, deps=["scan"])

report = SequentialRunner().run(graph)
print(report.status("merge"), report.results.get("merge"))
```

依赖可以先引用后声明。

### 并行调度

```python
from jobdag import JobGraph, Scheduler

graph = JobGraph()
graph.add("scan", scan_fn)
graph.add("parse", parse_fn, deps=["scan"], retries=2, timeout=30.0)
graph.add("merge", merge_fn, deps=["parse"])

scheduler = Scheduler(graph, max_parallel=8)
report = scheduler.run()   # 失败/超时的下游记 skipped，无关分支照跑完
print(report.attempts)     # 每个落地节点的尝试次数（含重试）
```

- `max_parallel` 是并发上限，设 1 时执行序与 `SequentialRunner` 一致
- 节点失败或超时：自身记 `failed`，下游整支记 `skipped`，异常进 `report.errors`
- 任意线程调 `scheduler.cancel()`：未开工的记 `cancelled`，在跑的跑完照记，
  之后报告不再变化
- `CycleError` 的报错会点出环上的节点
- 超时的节点按失败记账，但线程无法强杀，底层调用会在后台跑到自然结束

## 运行

```bash
python3 demo.py                           # 顺序跑一张演示图
python3 -m unittest discover -s tests -v  # 行为基线
```
