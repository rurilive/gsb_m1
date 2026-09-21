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

- 退避：第 n 次失败后 `next_attempt_at = now + base_backoff * 2 ** (n - 1)`（指数退避），时刻全由注入 clock 计算，relay 不 sleep
- 死信：单条连续失败达 `max_attempts` 即置 `dead`，不再投递，也不再阻塞同聚合键的后续事件
- 租约：投递前 `claim(seq, owner, now, ttl)` 原子认领，租约期内其他 owner 抢不到；持有者崩溃则租约到期后他人接管，保证至少一次
- 顺序：同一聚合键严格按 seq 升序投递，前一条重试中或被租用则后续一律等待，进死信才放行
