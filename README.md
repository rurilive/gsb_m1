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
