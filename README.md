# shapeq

网关进程内的多租户限流器，纯标准库，无外部依赖。

## 现状

`shapeq/limiter.py` 提供固定窗口计数的 `FixedWindowLimiter`：

- `FixedWindowLimiter(limit, window, clock=time.monotonic)`：limit 为单窗口放行上限，window 为窗口长度（秒），clock 为注入时钟
- `allow(key)` — 放行返回 True 并占掉一个名额，超限返回 False
- `stats()` 返回 `allowed` / `rejected` / `keys` 计数快照
- 窗口按注入时钟对齐到 window 的整数倍，跨窗口自动重新计数；不同 key 配额互不影响
- 内部一把锁保护，多线程单操作安全

`shapeq/shaper.py` 提供令牌桶整形器 `TokenBucketShaper`：

- `TokenBucketShaper(shared_rate, shared_burst, tenant_rate=None, tenant_burst=None, timeout=0.0, max_queue=None, clock=time.monotonic)`
- `acquire(tenant)` 返回 `Request`：`granted` 即时放行，`queued` 已入队，`rejected` 拒绝（`reason` 为 `bucket_full` / `queue_full` / `timeout`）
- 令牌按速率惰性补充、桶容量吸收突发；`timeout>0` 时超额请求进逐租户 FIFO 队列等待，等过上限结算为超时，`timeout=0` 即超额即拒
- `pump()` 按注入时钟结算队列；`stats()` 返回 `tokens` / `granted` / `rejected` / `timed_out` / `waiting` / `queues` / `tenants`

## 实现说明

1. 放行一个请求须同时从共享后端桶与租户公平桶各取一枚令牌；租户长期速率被自己的桶限定，打满也吃不到别人。
2. 租户桶是静态份额（按 tenant_rate 配），牺牲空闲租户间的再分配，换取不互相挤占的确定性。
3. 队列逐租户 FIFO，结算按 round-robin 每轮每租户至多放一个，突发补充也严格交替、无人插队。
4. 等待上限取等号：`now <= submitted_at + timeout` 且令牌够就放行，只在严格超时后拒，边界与窗口语义一致。
5. 令牌按注入时钟惰性补充并封顶桶容量；stats 会先结算再出快照，测试无需真实时间。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_limiter.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 固定窗口计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
