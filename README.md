# flowcap

flowcap 是一个无外部依赖的 Python 限流小库，当前版本只提供一个最朴素的限流原语。

## 现状

包内只有 `CounterLimiter`，它维护一个只增不减的累计计数器：在生命周期内最多放行 limit 次请求，超过之后一律拒绝。没有时间概念，没有窗口，不会按时间恢复，也没有按键分桶或等待能力。这个基线行为由 `tests/test_limiter.py` 锁定。

## 目标（见任务描述）

把 flowcap 从累计计数扩展成滑动窗口限流，并补齐令牌桶、按键分桶与等待预报能力，全部仍留在 flowcap 包内，且只用标准库。具体口径见任务描述。

## 运行

```
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
