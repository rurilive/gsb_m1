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

- `close(grace_timeout=None)` 优雅关闭：调用起 `submit` / `map` 抛 `PoolClosed`（定义在 `workerpool` 内）
- `grace_timeout=None` 无限等全部已提交任务落定；给时限则等到期，未落定者（含排队的）标记 `CANCELLED`
- 取消的排队任务不再执行；在跑任务无法安全打断，任其跑完但状态不再翻转，`result()` 抛 `CancelledError`
- 关闭报告为 `{"completed": 本次落定任务数, "cancelled": 未完成句柄列表}`，也支持属性访问
- 重复 `close()` 幂等，始终返回首次报告
- `WorkerPool(size, atexit=True)`（默认）注册 `atexit` 钩子，退出时按无时限 `close()` 收尾，`atexit_registered` 可查
