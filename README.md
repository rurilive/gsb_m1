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

## 实现说明

- 回收按对象在 `take` 写入时自动触发，只扫该对象自己的序列；`gc_interval` 节流，同一对象不足间隔不重扫，`gc()` 可手动全量回收。
- 判断顺序：先算当前时刻，快照年龄 `<= recent_seconds` 全部保留；再往前 `<= hourly_seconds` 的每个时钟小时只留桶内最后一张；更早的每个自然天只留当天最后一张，长期保留。
- 两档边界均为闭区间，恰好等于阈值归入更近的一档；小时/天桶按 3600/86400 秒整除对齐，注入时钟同样适用。
- `pin(obj, ts)` 按住的快照优先级最高：三档抽稀一律绕开，也不计入 `max_snapshots` 条数兜底；上限只从最旧的未按住快照继续丢。
- `gc_stats()` 可查回收轮数、上轮释放条数、累计释放条数与最近回收时刻；未配置 `RetentionPolicy` 时行为与旧版完全一致，不做回收。
