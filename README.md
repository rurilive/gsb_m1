# tracectx

批处理作业里的跨线程执行小工具：批量并发、后台单任务、并发闸门。纯标准库，无外部依赖。

## 模块

- `tracectx/batch.py` — `map_batch(fn, items, workers=4)`：切片并发处理，结果与输入同序；单条失败放 `ItemFailure(item, error)` 占位，不拖垮整批；`first_failure(results)` 取第一个失败
- `tracectx/detached.py` — `run_detached(fn, *args, timeout=None)`：后台线程执行，异常原样重抛，超时抛 `TimeoutError`；`async_call(fn, *args, on_done=None, on_error=None)`：回调式 fire-and-forget，返回线程句柄
- `tracectx/gate.py` — `Gate(max_active)`：并发上限闸门，`enter(timeout)` / `leave`，也可作上下文管理器
- `tracectx/tracing.py` — 跨线程调用链上下文：`start_trace(name, trace_id=None, slow_threshold=None)` 开启链路，`span(name)` 嵌套计时，`TracedThread` / `TracedThreadPoolExecutor` / `wrap` 传播上下文，`trace.report()` / `trace.print_report()` 输出树形汇总

## 约定

- 各模块的接口与语义以 docstring 为准，行为基线见 `tests/`。
- 纯标准库，Python 3.8+。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 上下文语义

### id 传播

- 链路 id 在入口生成：`start_trace("job")` 用 `uuid4().hex` 生成 correlation-id，也可显式传 `trace_id=` 复用上游 id；`current_trace_id()` 在任何线程内读取当前链路 id。
- 上下文在线程隔离的 `contextvars` 上：`TracedThread` 在构造时抓取当前线程的上下文快照，`run` 时在工作线程恢复；`TracedThreadPoolExecutor` 在每次 `submit`（含 `map`）时抓快照；`wrap(fn)` 把快照打包进普通可调用对象，供裸线程 / 回调使用。
- 快照在任务派发时定格，之后工作线程里的 id 与派发时一致；多条链路并发（含共用一个线程池）各自携带各自的 id，互不串号。快照是复制不是共享，任务内新开 / 退出 span 不影响派发线程的当前 span。
- `map_batch`、`run_detached`、`async_call`（含 `on_done` / `on_error` 回调）内部均使用 `TracedThread`，在链路内调用时自动传播 id；不做任何包装的裸 `threading.Thread` 不传播，线程内读到 `None`。

### span 嵌套

- `with span("name")` 创建的子 span 自动挂到当前 span 下，退出 with 时用 `time.monotonic()` 计时闭合；根 span 在 `start_trace` 时打开，与链路同名，退出链路 `with`（或 `trace.close()`）时闭合。
- 跨线程归位：工作线程里创建的 span 挂到「派发那一刻」派发线程的当前 span 下，因此 `map_batch` 各条目 span 是批处理 span 的兄弟 / 子节点，树结构不随线程调度错乱。
- 嵌套耗时满足包含关系：父 span 的 `duration` 不小于任一子 span。线程内也可手动 `trace.new_span(name, parent=...)` + `begin()` / `finish()`；未闭合的 span 在报告里标 `RUNNING` 并按已过时间显示。
- 没有活动链路时，`span(...)` 与 `current_span()` 返回空操作对象，不计时、不挂树、不报错，库代码可以无条件埋点。

### 慢阈值行为

- `slow_threshold` 在链路基线配置，单位秒，对全链路所有 span 生效；`span(name, slow_threshold=...)` 可为单段覆盖。
- span 闭合时若 `duration > slow_threshold`（严格大于）即打慢标记 `SLOW`；慢标记沿树原样展示，不向上冒泡（父 span 是否慢只看它自己的耗时与阈值，例如下游并发导致父段整体变慢时父段也会各自命中阈值）。
- `slow_threshold=None`（默认）永不标慢；`slow_threshold=0` 时所有实际执行过的 span 都标慢。
- 报告按嵌套层级缩进，每个 span 一行：`name`、monotonic 耗时（秒，三位小数）、标记（`SLOW` / `RUNNING`），首行是链路名与 correlation-id；`trace.print_report()` 收尾一次打出整棵树。
