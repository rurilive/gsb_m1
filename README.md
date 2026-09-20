# snapkeep

设备状态的进程内快照暂存，纯标准库，无外部依赖。

## 现状

`snapkeep/snapshots.py` 提供 `SnapshotStore`：

- `SnapshotStore(clock=time.monotonic)`：clock 为注入时钟，测试可传假时钟
- `take(obj, state)`：给 obj 存一张当前时刻的快照，返回该快照时间戳
- `get(obj, ts)`：取「不晚于 ts」的最近一张快照，没有则返回 None
- `list(obj)`：返回 obj 全部快照时间戳，升序
- 每个对象的快照序列相互独立，内部一把锁保护，多线程单操作安全

## 问题

几千台设备每隔几分钟拍一次，快照只进不出，内存持续膨胀。既要有保留策略把老快照回收掉，又不能误删还在被引用的那几张。

## 目标

见任务描述。约束：

- `take` / `get` / `list` 现有行为与 `tests/test_snapshots.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 连拍与按时刻读取
python3 -m unittest discover -s tests -v # 行为基线测试
```
