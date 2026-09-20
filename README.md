# winagg

规则引擎的进程内事件指标聚合，纯标准库，无外部依赖。

## 现状

`winagg/window.py` 提供 `EventCounter`：

- `EventCounter(clock=time.monotonic)`：clock 为注入时钟，用来记事件的到达时刻
- `add(ts, v=1)`：记一个事件，ts 为事件时间，v 为计数增量，返回累计总和
- `total()`：已记录事件的计数总和；`count()`：已记录事件条数
- `span()`：已记录事件的时间跨度 `(最早, 最晚)`，没有事件时返回 None
- `last_arrival()`：最近一次 add 的到达时刻，没有事件时返回 None
- `reset()`：清空全部事件与计数
- 事件时间不要求递增，乱序到达原样入账，增量允许为负
- 事件按到达顺序存在列表里，只追加不淘汰；内部一把锁，多线程单操作安全

## 问题

事件只加不减，线上跑久了内存一路涨；也没有只看最近一段时间的口径，迟到的事件混进来更分不清该不该算。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_window.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 累计计数 + 滑动窗口演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- `SlidingWindow(size, bucket)`：最近 size 秒的计数窗口，按 bucket 分桶，size 必须是 bucket 的整数倍
- 窗口按事件时间推进：水位线 = 见过的最大事件时间，左缘 = 水位线 - size，与到达时钟无关，重放可复现
- 窗口左闭（含左缘）；桶与 closed 产出区间一律闭开 `[start, end)`，相邻产出首尾相接
- 乱序判定：ts >= 左缘正常入账（落入对应桶），ts < 左缘判迟到，按 on_late 丢弃或留档，均计入 late_count/late_total
- 淘汰是真实删除：整桶滑出窗口时聚合成 `WindowResult` 写入 closed()，跨左缘的桶先剪掉界外事件
- `merge_closed()` 只合并 end == start 且未过 closed_retention 保留期的相邻产出
- `WindowSet` 多窗口并行：每个窗口各自维护水位线与桶，各自独立淘汰，短的到点就走
