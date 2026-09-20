# shapeq

网关进程内的多租户限流器，纯标准库，无外部依赖。

## 现状

`shapeq/limiter.py` 提供固定窗口计数的 `FixedWindowLimiter`：

- `FixedWindowLimiter(limit, window, clock=time.monotonic)`：limit 为单窗口放行上限，window 为窗口长度（秒），clock 为注入时钟
- `allow(key)` — 放行返回 True 并占掉一个名额，超限返回 False
- `stats()` 返回 `allowed` / `rejected` / `keys` 计数快照
- 窗口按注入时钟对齐到 window 的整数倍，跨窗口自动重新计数；不同 key 配额互不影响
- 内部一把锁保护，多线程单操作安全

`shapeq/shaper.py` 提供按速率整形的 `TokenBucketShaper(capacity, refill_rate, overflow="queue", max_wait=1.0, clock=time.monotonic)`：

- `acquire(tenant, tokens=1)` 返回 `Ticket`：`ready` 立即放行，`queued` 排队等补充，`rejected` 当场被拒
- `pump()` 在注入时钟推进后按 FIFO 放行各租户到期的排队请求，返回翻成 `ready` 的 Ticket
- `stats()` 返回 `allowed` / `rejected` / `queued` 与每租户剩余 `tokens`
- 每租户独立令牌桶与队列，配额互不挤占；令牌按时钟惰性补充，无后台线程

## 问题

下游要的是流量整形而不是简单挡回：突发要能被吸收、平常要按速率放。多租户共用一份后端配额时，某个租户突发打满会挤掉其他租户的份额。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_limiter.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 固定窗口计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 令牌桶与固定窗口并存于 `shapeq/shaper.py` 的 `TokenBucketShaper`，老接口语义不变。
- 补充完全惰性：按注入时钟的时间差在每次操作时补算，无后台线程，补充点可精确测试。
- 公平取静态切分：每租户独立桶与 FIFO 队列，租户打满只欠自己的债，绝不吃别人份额。
- 取舍：空闲租户的份额不转借，牺牲部分总利用率换取隔离性与结果可预测。
- 溢出双策略：`queue` 按补充速率排队（`max_wait` 封顶，预计等不到当场拒），`reject` 立即拒。
- 排队请求在时钟推进后用 `pump()` 取出，结果写在 `Ticket` 上，无需真实 sleep。
- `stats()` 含 `allowed`/`rejected`/`queued` 与每租户剩余 `tokens`。
