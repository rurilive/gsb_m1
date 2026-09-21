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
吞吐（1 秒窗口切 20 格，0.05 秒滚一格），`tracesamp/controller.py` 的
`RateController` 按窗口读数调整采样率。`tracesamp/clock.py` 的
`ManualClock` 是可手动推进的假时钟，测试和演示拿它把时间点卡准。

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

## 实现说明（自适应模式）

自适应模式重做后，**决策、统计、调档**三件事彻底分开，各自用各自的锁，
热路径上没有全局大锁。

### 决策怎么定

- 每个 `trace_id` 先经 crc32 + 64 位雪崩混合（splitmix64 收尾）落到
  `[0, 1)` 的稳定小数 `trace_unit`，不依赖进程 hash 种子，连续命名的
  trace_id 在小集合上也近似均匀。
- 一条 trace 第一次出现时，比较 `trace_unit < 当前采样率` 得到结论，
  结论存入按 `trace_unit` 分 32 片的决策缓存；同一条 trace 后续的 span，
  无论隔几秒到还是几十路并发同时到，都在片内小锁下复用同一结论，
  采就整条采、丢就整条丢。
- 缓存条目带 5 秒 TTL（`decision_ttl` 可调），写入时惰性过期，不做任何
  周期性全表扫描；每片另有 16384 条硬上限兜底，先删过期、再删最早，
  长尾 trace_id 不会把内存撑爆。

### 阈值（采样率）怎么调

- 每个 span 只做两次很轻的记账：决策计数经 `SlidingWindow.add2` 原子
  写入同一桶（`sampled` 永远是 `total` 的子集），进程级累计数由另一把
  小锁维护。窗口本身按桶时间戳惰性失效：滚格只让旧桶自然滑出，不再
  一滚就清空整窗，因此读数覆盖的是完整的最近 1 秒。
- 调档每 `window/10`（默认 0.1 秒）最多推进一次：推进线程对窗口取一次
  total/sampled 的**多键原子快照**（同一锁内读出，两个计数不可能读岔），
  并按快照里桶的实际覆盖时长归一；冷启动窗口没装满时按真实覆盖秒数算
  每秒均值，不被完整窗口稀释。控制推进有独立锁和二次时间校验，并发
  span 不会把同一拍推进多次。
- `RateController` 用**前馈为主、弱反馈纠偏**的对称控制律：
  目标档位 = `target_per_sec / 总吞吐`，夹在 `[0.001, 1.0]`，流量上涨
  降档和峰值过去回升走同一条线性路径；实际 sampled 与目标的比值只做
  30% 比例的纠偏（修正因子夹在 [0.5, 2]），消掉 trace 散列的小幅系统
  偏差但不放大窗口噪声；每次只朝目标走 50% 的步长。某窗 sampled 为 0
  不再把档位一把拍回 1.0，窗口没流量则档位保持不动，因此平稳流量下不
  会一惊一乍，峰值过去也沉得回来，不会再钉在 1.0。
- 重新切入自适应模式会重置窗口读数、控制器档位和决策缓存，不背上一次
  模式的旧账；静态模式的代码路径与语义保持原样，一字未动。
