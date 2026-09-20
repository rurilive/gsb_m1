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
python3 demo.py                          # 累计计数演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
