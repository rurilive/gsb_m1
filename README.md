# outboxd

事务性发件箱与中继，纯标准库，无外部依赖。

## 现状

`outboxd/outbox.py` 提供进程内实现的发件箱：

- `MemoryStore`：内存发件箱表，`append` / `rows` / `pending` / `get` / `mark_sent`，seq 从 1 起单调递增，代表记录序
- `Outbox(store, sender, clock=time.monotonic)`：`record(aggregate, kind, payload)` 落库并返回 seq；`relay()` 扫描待发事件逐条投递，成功标记已发，失败保留待重试，返回本次成功投递条数
- `sender` 需实现 `send(row)`，抛异常即视为投递失败
- `aggregate` 是聚合键，也是分区键；同一聚合键的事件按 seq 升序即其发生顺序
- store / sender / clock 全部注入，进程内无真实 IO

## 问题

`relay()` 只是逐条尽力投递，失败就跳过留待下次，缺可靠投递保证：重试没有间隔、毒消息会无限占用、并发中继可能重复投递，同一聚合键还会因重试乱序。

## 目标

见任务描述。约束：

- 现有接口与 `tests/test_outbox.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 落库与投递演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 退避：第 n 次连续失败后，下次可投递时刻 = 失败时刻 + `min(cap, base * factor ** (n - 1))`，默认 base=1s、factor=2、cap=60s，全部用注入时钟计算，不 sleep
- 死信：连续失败达 `max_attempts`（默认 5）即置 `dead`，移出待发队列、不再投递，可经 `store.dead()` 查看
- 租约：投递前 `claim(seq, owner, now, ttl)` 认领，租约未过期其他中继认领失败，同一条不会被并发重投；失败或成功即释放，租约到期自动失效
- 顺序：同一聚合键严格按 seq 升序投递，前一条未成功（退避中、被他人租用或刚失败）时同键后续本轮一律跳过；不同聚合键互不阻塞
- 至少一次：成功才 `mark_sent`，崩溃或租约丢失可能导致重复投递，消费方需幂等
