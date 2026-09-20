# workerpool

后台作业执行框架的固定线程池，进程内嵌，纯标准库，无外部依赖。

## 接口约定

`workerpool/pool.py` 提供 `WorkerPool(size)`：`size` 个常驻工作线程共享一个任务队列。

- `submit(fn, *args, **kwargs)` 立即返回 `Task` 句柄，不等待执行
- `Task` 句柄：`state`（pending / running / finished / failed）、`done`、`seq`（提交序号）、`wait(timeout)`、`result(timeout)`、`exception(timeout)`；任务内异常在工作线程被兜住，从 `result()` 原样抛出，不影响后续任务
- `map(fn, *iterables)` 批量提交，按提交顺序返回全部结果
- 并发上限即 `size`：多余的提交在队列里排队
- `tasks` 返回全部已提交句柄的元组快照，按提交顺序

## 目标

见任务描述。约束：

- `tests/test_pool.py` 是行为基线，一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 关闭语义

- `close(grace_timeout=None)` 拒收新任务：`submit`/`map` 抛 `PoolClosed`
- 无时限：等全部已提交任务落定；有时限：到期未落定者（含排队中的）标记 `cancelled`，不再执行、状态不再翻转
- 返回 `ShutdownReport(completed, cancelled)`：本次落定的任务数与未完成句柄列表
- 重复 `close` 幂等，返回首次报告
- `WorkerPool(size, atexit=True)` 退出时按 `close()` 语义自动收尾，`atexit_registered` 可查
