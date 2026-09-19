# metricbox

进程内指标收集的直方图模块，纯标准库，无外部依赖。

## 现状

`metricbox/histogram.py` 提供线程安全 `Histogram`（`threading.Lock` + list）：

- `observe(value)` 记录一个样本
- `count()` 返回样本总数
- `percentiles(*fractions)` 返回 `{分位: 值}`，按 (n-1) 线性插值；无样本抛 `ValueError`

样本永久保留，没有时间窗口。

## 问题

直方图的数据是全生命周期的。流量模式一变（刚扩容、刚切流），旧样本把分位数拖住，监控看到的 P99 迟迟反映不了现状，告警跟着失真。

## 目标

见任务描述。约束：

- `tests/test_histogram.py` 是行为基线，一个字不改
- 不配置窗口时行为与现状完全一致
- 纯标准库

## 运行

```bash
python3 demo.py                          # 直方图演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- `window_seconds=None` 走 list 全量路径，行为不变；配置后用 deque 存 `(时间戳, 值)`。
- 窗口判定：`now - 时间戳 <= window_seconds` 算窗口内，恰满窗口的样本保留。
- `clock` 可注入（无参可调用对象），默认 `time.monotonic`；不另起后台线程。
- `count`/`percentiles`/`snapshot` 惰性按当前时间过滤，不删旧样本；`observe` 顺带挤出队首旧样本。
- `observe` 与 `compact()` 返回本次物理清理的样本数。
- `snapshot(bucket_edges)` 要求边界严格递增，值等于边界归右桶（左闭右开），首尾各一个溢出桶。
- 所有读写都在同一把锁内。
