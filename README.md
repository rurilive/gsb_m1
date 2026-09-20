# tracectx

批处理作业里的跨线程执行小工具：批量并发、后台单任务、并发闸门。纯标准库，无外部依赖。

## 模块

- `tracectx/batch.py` — `map_batch(fn, items, workers=4)`：切片并发处理，结果与输入同序；单条失败放 `ItemFailure(item, error)` 占位，不拖垮整批；`first_failure(results)` 取第一个失败
- `tracectx/detached.py` — `run_detached(fn, *args, timeout=None)`：后台线程执行，异常原样重抛，超时抛 `TimeoutError`；`async_call(fn, *args, on_done=None, on_error=None)`：回调式 fire-and-forget，返回线程句柄
- `tracectx/gate.py` — `Gate(max_active)`：并发上限闸门，`enter(timeout)` / `leave`，也可作上下文管理器
- `tracectx/trace.py` — 跨线程调用链上下文：`begin_chain()` 开链路，`span(name)` 计时，`TracedThread` / `TracedThreadPoolExecutor` 负责跨线程传播，`chain.report()` 出树形报告

## 约定

- 各模块的接口与语义以 docstring 为准，行为基线见 `tests/`。
- 纯标准库，Python 3.8+。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 上下文语义

- **id 传播**：`with begin_chain() as chain:` 在入口生成 correlation-id（缺省 uuid4 hex，也可显式传入），链路内 `correlation_id()` 可取。`TracedThread`（`start` 时）与 `TracedThreadPoolExecutor`（`submit` 时）快照当前上下文，任务在别的线程里看到的是提交方那一刻的链路；`map_batch` / `run_detached` / `async_call` 内部已用 `TracedThread`，链路自动穿透。每个线程持有上下文副本，并发链路互不串号；链路内再开链抛 `RuntimeError`。
- **span 嵌套**：`with span("name"):` 用 monotonic 钟计时，子 span 挂到当前 span 下；跨线程开出的 span 也归位到父 span 的 `children` 里（按开始顺序）。退出后 `span.elapsed` 定格耗时，`current_span()` 回到上一层。链路外单独用 `span()` 会隐式开一条链，根 span 退出时自动收尾。
- **慢阈值**：`set_slow_threshold(seconds)` 配全局阈值（默认 0.5s），`span(name, slow_threshold=...)` 可单个覆盖；耗时 >= 阈值的 span 置 `slow=True`。`chain.report()` 按嵌套层级缩进输出整棵树，每行 `name 耗时ms [SLOW]`，收尾打一次即可定位慢段。
