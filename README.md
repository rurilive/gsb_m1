# outboxd

事务性发件箱与中继，纯标准库，无外部依赖。

## 现状

`outboxd/outbox.py` 提供进程内实现的发件箱：

- `MemoryStore`：内存发件箱表，`append` / `rows` / `pending` / `get` / `mark_sent`，seq 从 1 起单调递增，代表记录序
- `Outbox(store, sender, clock=time.monotonic)`：`record(aggregate, kind, payload)` 落库并返回 seq；`relay()` 扫描待发事件逐条投递，成功标记已发，失败保留待重试，返回本次成功投递条数
- `sender` 需实现 `send(row)`，抛异常即视为投递失败
- `aggregate` 是聚合键，也是分区键；同一聚合键的事件按 seq 升序即其发生顺序
- store / sender / clock 全部注入，进程内无真实 IO

可靠投递（退避重试、死信、租约互斥、聚合键内严格有序）已在 `relay()` 实现，行为见文末「实现说明」与 `tests/test_relay.py`。约束：

- 现有接口与 `tests/test_outbox.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 落库与投递演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

1. 退避：第 n 次失败（n 从 0 起）后 `not_before = now + min(base_delay * 2**n, max_delay)`，默认基数 1s、上限 30s；`relay()` 不 sleep，未到时刻的条目跳过，时刻全由注入 `clock` 判定。
2. 死信：同一条累计失败达到 `max_attempts`（默认 5）即置 `dead` 离开待发，中继不再重试，用 `store.dead()` 查看。
3. 顺序：待发按 seq 全局升序扫描；同一聚合键只放行队头，前一条未成功（待退避）后一条绝不抢先；成功或进死信后当场放行后续，不同聚合键互不阻塞。
4. 租约：投递前按行原子认领（`claim(seq, worker_id, now, lease_seconds)`，默认 30s），他人租约未到期抢不到，并发中继不会重复投同一条；租约凭注入时钟到期可被接管，持有者崩溃不会永久卡死。
5. 语义：成功才标 `sent`，任何失败都保留重试或进死信，保证至少一次；租约超时被接管的极端情况下仍可能重复投递，下游需幂等。
