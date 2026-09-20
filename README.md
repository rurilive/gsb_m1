# tracectx

批处理作业里的跨线程执行小工具：批量并发、后台单任务、并发闸门。纯标准库，无外部依赖。

## 模块

- `tracectx/batch.py` — `map_batch(fn, items, workers=4)`：切片并发处理，结果与输入同序；单条失败放 `ItemFailure(item, error)` 占位，不拖垮整批；`first_failure(results)` 取第一个失败
- `tracectx/detached.py` — `run_detached(fn, *args, timeout=None)`：后台线程执行，异常原样重抛，超时抛 `TimeoutError`；`async_call(fn, *args, on_done=None, on_error=None)`：回调式 fire-and-forget，返回线程句柄
- `tracectx/gate.py` — `Gate(max_active)`：并发上限闸门，`enter(timeout)` / `leave`，也可作上下文管理器

## 约定

- 各模块的接口与语义以 docstring 为准，行为基线见 `tests/`。
- 纯标准库，Python 3.8+。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
