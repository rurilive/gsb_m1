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
