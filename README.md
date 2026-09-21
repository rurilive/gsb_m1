# tracesamp

进程内的链路追踪采样器，纯标准库，无外部依赖。网关和各个 worker 各持一个
`TraceSampler`，每个 span 到达时拿 trace_id 问一次要不要采。

## 现状

`tracesamp/sampler.py` 提供 `TraceSampler`：

- `TraceSampler(rate=0.1, mode="static", target_per_sec=100.0, window_seconds=1.0, clock=time.monotonic)`
- `should_sample(trace_id)`：这条 trace 的 span 要不要采，返回 bool
- `set_mode(mode)` / `mode`：在 "static" 和 "adaptive" 之间切
- `rate()`：当前生效的采样率
- `stats()`：mode、rate、target_per_sec、total、sampled、dropped、窗口读数、updates

两个模块配合它工作：`tracesamp/window.py` 的 `SlidingWindow` 按窗口统计每秒
吞吐（窗口切两格，半秒滚一格），`tracesamp/controller.py` 的 `RateController`
按窗口读数调整采样率。`tracesamp/clock.py` 的 `ManualClock` 是可手动推进的
假时钟，测试和演示拿它把时间点卡准。

## 语义约定

静态模式：按构造时给的比例采，不看流量，也不看 target_per_sec。

自适应模式：target_per_sec 是期望的每秒采样条数，按这个数备的容量。流量高出
目标时把每秒采样条数贴着目标采，流量低于目标时全采（采样率上限 1.0）。

两种模式共用的约定：一条 trace 的 span 可能隔几秒才到齐，也可能同时挤进来，
它们的采样结论必须一致，采就整条采，丢就整条丢。

## 问题

自适应模式上线后监控上冒出来的现象：平稳流量下每秒采样条数长期高出目标好几
倍；采样率忽高忽低，有时直接钉在 1.0 不动；同一条 trace 的 span 一半采了
一半丢了；拿流量回放跑，采样量稳不下来。

## 目标

见任务描述。约束：

- 对外方法签名与静态模式的语义保持不变
- `tests/` 是行为基线，一个字不改，必须原样全绿
- 纯标准库，不引三方

## 运行

```bash
python3 demo.py                          # 现状演示：四个现场
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

自适应模式拆成三块，各管各的：`SlidingWindow` 只负责统计，`RateController`
只负责调采样率，`TraceSampler` 只负责下决策。

**决策怎么定。** 自适应和静态用同一套比法：`trace_id` 过 crc32 落到
[0, 1) 的稳定小数，跟当前采样率比大小，不给随机数留位置。算出来的结论连
同一个过期时刻存进决策缓存（TTL 取 10 秒和 5 个窗口的较大者，条目数有上
限，满了先清过期再挤最旧的），之后这条 trace 的 span 无论隔几秒到、多少
个一起挤进来，都直接读缓存里的同一个答案；缓存期间采样率怎么调都不影响
已经在路上的 span。

**统计怎么读。** 窗口按固定的桶格滚动，换格时只清被复用的那一桶，其余桶
里的数据还在窗口内。喂给控制器的 total 和 sampled 在同一把锁里一次读出，
并且除以窗口当前真实覆盖的秒数（桶对齐会让覆盖时长在一格范围内浮动，直
接除窗口长度会系统性偏小，相位走到哪偏差就到哪）。

**阈值怎么调。** 每个控制点（窗口的三分之一）按窗口读数算出"要贴住目标
该有的采样率" `desired = target / total`，当前采样率分步往它靠：一步最
多翻一倍、最多砍一半；每秒采样条数落在目标上下 10% 的死区里就不动。超
了压、少了抬，两个方向都走得到，所以峰值过去流量回落时采样率能沉回来，
流量低于目标时稳稳停在 1.0 全采。采样率始终夹在 [min_rate, 1.0]。

**并发怎么扛。** 决策缓存、计数、窗口、控制点各用各的锁，控制点用
双重检查只放一路线程进去调率，热路径上没有一把大锁，单进程按每秒十万
span 的峰值留得出余量。
