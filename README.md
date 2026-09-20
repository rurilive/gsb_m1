# shapeq

网关进程内的多租户限流器，纯标准库，无外部依赖。

## 现状

`shapeq/limiter.py` 提供固定窗口计数的 `FixedWindowLimiter`：

- `FixedWindowLimiter(limit, window, clock=time.monotonic)`：limit 为单窗口放行上限，window 为窗口长度（秒），clock 为注入时钟
- `allow(key)` — 放行返回 True 并占掉一个名额，超限返回 False
- `stats()` 返回 `allowed` / `rejected` / `keys` 计数快照
- 窗口按注入时钟对齐到 window 的整数倍，跨窗口自动重新计数；不同 key 配额互不影响
- 内部一把锁保护，多线程单操作安全

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
