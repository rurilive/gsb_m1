# jobdag

任务依赖图调度底座，纯标准库，无外部依赖。内部补数链路和离线对账都挂在它上面。

## 包结构

- `jobdag/graph.py`：`JobGraph` 声明节点和依赖，`topo_order()` 压出执行序；
  错误类型 `DuplicateJobError` / `UnknownDepError` / `CycleError`
- `jobdag/runner.py`：`SequentialRunner` 按执行序单线程跑，失败即中断
- `jobdag/report.py`：`RunReport` 记逐节点终态、返回值、异常和耗时

## 用法

```python
from jobdag import JobGraph, SequentialRunner

graph = JobGraph()
graph.add("scan", scan_fn)
graph.add("merge", merge_fn, deps=["scan"])

report = SequentialRunner().run(graph)
print(report.status("merge"), report.results.get("merge"))
```

依赖可以先引用后声明；`RunReport.states` 里目前只有成功路径会落地。

## 运行

```bash
python3 demo.py                           # 顺序跑一张演示图
python3 -m unittest discover -s tests -v  # 行为基线
```
