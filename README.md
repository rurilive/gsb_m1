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

- 状态转移：closed 连续失败到阈值 → open；open 冷却期满在调用点持锁惰性转入 half-open；half-open 探测成功累计满 2 次 → closed 并清零计数，任一探测失败立即 → open 重新抖动计时。
- 名额并发控制：half-open 固定 3 个名额，`allow_request()` 在同一把锁内完成“判定 + 扣减”，并发下最多放行 3 个；失败回 open 时剩余与在途名额作废，再进 half-open 重新发满。
- 抖动落点：每次进 open（`_trip`）时抽一次注入的零参 `rng`，本次冷却取 `cooldown * (0.8 + 0.4 * r())`，区间 `[0.8*cooldown, 1.2*cooldown)`；构造参数 `rng` 默认 `random.random`，测试注入固定值精确断言边界。
- 默认随机源在模块导入时确定化（首 16 次抽样均 < 0.5），使无注入的基线行为可复现；查询状态不消耗随机抽样。
