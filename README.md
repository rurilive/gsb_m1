# breaker

网关进程内的下游依赖熔断器，纯标准库，无外部依赖。

## 现状

`breaker/core.py` 提供两态熔断器 `CircuitBreaker`：closed / open。连续失败达到阈值（默认 5）进入 open，冷却固定 30 秒后回到 closed。`clock` 通过构造参数注入（默认 `time.monotonic`），内部用 `threading.Lock` 保护状态。

接口：

- `allow_request()` — 当前是否放行
- `is_open()` — 是否处于断开
- `record_failure()` / `record_success()` — 上报结果

## 问题

冷却一到就直接闭合、全量放行。下游如果还没恢复，刚闭合立刻再次被打断开，来回震荡，每次震荡都伴随一波上游超时。

## 目标

见任务描述。约束：

- `tests/test_breaker.py` 是行为基线，一个字不改
- 时钟与随机源均可注入，测试不做真实 sleep
- 纯标准库

## 运行

```bash
python3 demo.py                          # 熔断与恢复演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

1. 三态转移：closed 连续失败达阈值 → open；open 冷却到期（惰性检查）→ half-open；half-open 累计 2 次探测成功 → closed，任一探测失败 → open。
2. half-open 只放行探测请求，名额固定 3 个：`allow_request()` 在同一把锁内判名额并自增，并发下不会超发；探测完成（成功）回收名额，失败则立即重开。
3. 半开失败回 open 时已发名额与成功计数全部作废，到期后是全新一轮 3 个名额。
4. 抖动落点：半开失败重开时取本次冷却 = `cooldown * (0.8 + 0.4 * r())`，区间 [0.8cooldown, 1.2cooldown)，每次重开重新抽样。
5. 首次熔断沿用基础 cooldown 不抽样，保证历史调用方的冷却时序确定；`clock` 与 `r`（默认 `random.random`）均可构造注入。
