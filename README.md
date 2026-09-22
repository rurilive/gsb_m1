# waitgraph

任务调度器的等待图库：登记谁在等谁手里的资源，回答有没有死锁、环上是谁。
纯标准库。

## 用法

```python
from waitgraph import ResourceRegistry

reg = ResourceRegistry()
reg.acquire(1201, "index")     # True：当场拿着
reg.acquire(1202, "index")     # False：排队等 1201 放
reg.health()                   # {"deadlocked": False, "cycle": []}
reg.release(1201, "index")     # 返回 1202，资源交给队头
```

- `ResourceRegistry(detector=None)` 等待关系的事实来源
  - `acquire(pid, resource)` 空着当场持有返回 True，被占进队等待返回 False；
    自己已经拿着或者已经在等同一个资源抛 `AlreadyHeld`
  - `release(pid, resource)` 放掉自己拿的资源，队头接手并返回接手者 pid；
    没拿着抛 `NotHeld`
  - `drop(pid)` 进程失联（崩溃、断连）：它排的队作废，它手里的资源直接
    收回不转交，等着这些资源的进程一并作废，返回作废的 `(pid, resource)`
  - `holder` / `waiters` / `pending` / `waits` / `holds` 查当前状态，
    `waits()` 是权威等待边 `(pid, resource, holder)`
  - `health()` 给运维探针：`{"deadlocked": 布尔, "cycle": 成员列表}`
  - `load_state(holds, waits)` 启动时从快照整体恢复，不做逐条检测
- `DeadlockDetector` 检测器，registry 每次等待关系变动都会喂事件给它
  （`note_wait` / `note_wake` / `note_drop`，启动加载走 `rebuild`）
  - `deadlocked()` 有没有死锁，`cycle_members()` 环上成员
  - `stats()` 检测过程的访问计数（遍历和整图枚举碰到的节点数），
    `reset_stats()` 归零，压测单次变动的开销时用它观测
- `waitgraph.oracle.FullScan(registry)` 全量参考：每次现读权威登记从零算，
  报告规则固定，作为检测器行为的对拍基准
- `WaitGraph` 底层拓扑与遍历原语（`walk` / `reachable` / `holders`），
  节点展开计入 `visits`，不带业务语义

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```
