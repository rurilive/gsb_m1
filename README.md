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

## 实现说明

- 滑动窗口按事件时间推进：watermark 为已见最大事件时间，与注入时钟（到达时刻）无关，重放可复现
- 滑动窗口覆盖 `[watermark - N, watermark]`，左闭；滚动产出窗口取闭开 `[start, end)`，ts 等于 end 归入下一段
- 乱序判定：ts < watermark - N 即出界迟到，按 late_policy 丢弃（记 dropped）或单独记迟到数（late），不默默吞
- 迟到但仍在窗口内的事件正常计入窗口和；淘汰是真删，watermark 推进时窗口外事件从缓冲移除
- 滚动窗口在 end <= watermark 时关闭，产出 ClosedWindow(start, end, total, count)，drain_emissions() 捞走补数
- 已关闭窗口的产出不再改；关闭后才到的同段事件只进滑动窗口和
- 多窗口（MultiWindow）各自维护独立缓冲与淘汰节奏，各扫各的，短窗口到点先走
- merge 仅允许 a.end == b.start 时间连续、且按 emission_retention 均未过期的两个已关闭窗口
