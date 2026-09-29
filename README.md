# schedx

任务调度小工具，纯标准库，无外部依赖。

## 现状

`schedx/plan.py` 提供 `FlatSched`：登记一组带时长与依赖的任务，然后回答几个最直白的问题。

- `add_task(name, dur, deps)`：登记任务，依赖必须已登记，重复登记抛 `DuplicateTask`
- `add_dep(name, dep)`：后置补一条依赖边，两端都要已登记，可以引入环
- `ready_tasks(done)`：线性扫描全部任务，挑出依赖都已完成的
- `topo_order()`：朴素逐轮扫描，每轮找出依赖已满足的任务，求一个拓扑序，成环抛 `SchedError`
- `total_time_serial()`：把全部时长线性求和
- `can_finish(name, done)`：递归判断传递前置是否都已完成

`SchedError` 是错误基类，`UnknownTask`、`DuplicateTask` 都继承它。

## 问题

现状只有串行口径：每轮查询都从头重扫全部任务，任务之间没有并行概念，也没有资源（并行度）约束，因此答不了最短完工时间，也无法在依赖成环时给出成环位置。

## 目标

见任务描述。约束：

- `tests/test_plan.py` 是行为基线，一个字不改且必须全绿
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 现状能力演示
python3 -m unittest discover -s tests    # 行为基线测试
```

（实现后补，10 行以内）
