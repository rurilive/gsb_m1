# taskheap

带优先级的任务队列，纯标准库，无外部依赖。调度侧把待执行的任务提交进来，
执行侧循环取任务，跑失败的任务放回队列等下一轮。

## 用法

```python
from taskheap import TaskQueue

queue = TaskQueue()
queue.push("render", 3)      # 提交任务，优先级数字越小越先执行
queue.push("index", 1)
queue.push("export", 3)

task_id = queue.pop()        # "index"，弹出即进入执行中
queue.done(task_id)          # 执行成功，收尾
queue.update_priority("render", 0)   # 在线调整优先级
batch = queue.pop_batch(2)   # 批量弹出，按弹出顺序返回任务号
queue.release(batch[0])      # 执行失败，放回队列
queue.pending()              # 排队中的任务号，按下一轮弹出顺序
```

## 接口

- `TaskQueue.push(task_id, prio)`：提交任务，重复提交同一个任务号抛 `ValueError`，prio 不是 int 抛 `TypeError`
- `TaskQueue.pop()` / `pop_batch(count)`：弹出下一个（或下一批）该执行的任务，队列空时返回 `None` / 短列表
- `TaskQueue.done(task_id)`：执行成功收尾，任务不再回到队列
- `TaskQueue.release(task_id)`：执行失败放回队列，等下一次被弹出
- `TaskQueue.update_priority(task_id, prio)`：在线调整优先级
- `TaskQueue.pending()` / `running()` / `queued(task_id)` / `size()`：观察队列
- `TaskQueue.capacity()`：后备存储的槽位数，给内存观察用
- `SortedListQueue`：排序列表参考实现，接口同上，直白但慢，只用来做小规模对照

`taskheap/heap.py` 的 `IndexedHeap` 是队列底下的二叉最小堆，`heap.HeapEntry`
是堆里的一条记录，`key()` 决定谁先出堆。`taskheap/naive.py` 是参考实现。

## 语义约定

- 弹出顺序：优先级数字小的先出；同优先级按提交序号先来后到，提交序号在
  `push` 时定下，调优先级和回滚都不重置它。
- `update_priority`：只对排队中的任务有效，其余情况抛 `KeyError`；调成当前
  一样的优先级等于没调，不影响任何顺序。
- `release`：只对执行中的任务有效，其余情况抛 `KeyError`；放回的记录保留
  它当前的优先级和原来的提交序号。
- `done`：只对执行中的任务有效，其余情况抛 `KeyError`。
- 同一个任务在同一时刻只应出现在一个位置，也不会被执行两遍。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
python3 bench.py [队列规模] [操作条数]    # 跟参考实现的吞吐对照，默认三千条常驻、十万次混合操作
```

## 目录

```
taskheap/heap.py    二叉堆实现
taskheap/queue.py   任务队列状态流转
taskheap/naive.py   排序列表参考实现
tests/              行为基线
demo.py             现状演示
bench.py            吞吐对照
```
