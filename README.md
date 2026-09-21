# stealpool

采集管线在用的进程内任务池，纯标准库，无外部依赖。

## 现状

`stealpool/pool.py` 提供 `Pool(workers=None, name="stealpool")`：

- `submit(fn, *args, **kwargs)` 提交任务返回 `Future`；worker 数默认取 CPU 核数
- 任务统一进一个全局队列，哪个 worker 空闲哪个来取，和提交它的线程不绑定
- `shutdown(wait=True)` 关闭并等在跑的任务收尾，可重复调用；关闭后提交抛 `PoolClosed`
- `stats()` 返回快照：submitted / completed / failed / steals，以及每个 worker 的
  busy_seconds / idle_seconds / tasks
- 支持 `with Pool(...) as pool` 写法

`stealpool/future.py` 提供 `Future`：

- 状态从 PENDING 到 RUNNING 再到 FINISHED；还在 PENDING 的可以 `cancel()`，进 CANCELLED
- `result(timeout=None)` 阻塞取结果，任务抛过异常就重新抛出，等超时抛 `TimeoutError`，
  被取消的任务抛 `TaskCancelled`；`done()` / `cancelled()` / `running()` / `state()` 查状态
- `add_done_callback(fn)` 在结束或取消时回调

`stealpool/reference.py` 提供任务树的顺序参考实现：

- `TaskNode(name, children=(), work=0.0, tag=0)`：节点结果等于 tag 加子节点结果之和，
  work 是模拟 IO 的耗时秒数，由注入的 sleep 消耗
- `run_sequential(root, sleep=time.sleep, order=None)`：单线程按后序跑完整棵树，
  返回 name 到结果的字典，order 记录完成顺序
- `random_tree(seed, depth=3, fanout=3, leaf_work=0.0)`：确定性随机任务树
- `TreeRunner(pool, sleep=time.sleep).run(root)`：每个节点一个任务，子节点由父任务
  submit 后取结果，返回和 `run_sequential` 同形状的字典

## 问题

一个解析任务派生出的下载子任务全进全局队列，被任意线程抢走，线程本地攒的站点会话
和连接缓存用不上；长任务扎堆时负载不匀；递归派生出的任务偶尔等不回来；取消一条链
时，已经派生出去、还没开跑的子任务不会跟着作废。

## 目标

见任务描述。约束：现有接口与 `tests/` 下的基线保持不变（基线一个字不改），纯标准库。

## 运行

```bash
python3 demo.py                          # 提交取结果、任务树对拍、取消演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
