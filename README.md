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
吞吐（窗口切四格，1/4 秒滚一格，只清滑出窗口的老桶），
`tracesamp/controller.py` 的 `RateController` 按窗口读数调整采样率。
`tracesamp/clock.py` 的 `ManualClock` 是可手动推进的假时钟，测试和演示
拿它把时间点卡准。

## 语义约定

静态模式：按构造时给的比例采，不看流量，也不看 target_per_sec。

自适应模式：target_per_sec 是期望的每秒采样条数，按这个数备的容量。流量高出
目标时把每秒采样条数贴着目标采，流量低于目标时全采（采样率上限 1.0）。

两种模式共用的约定：一条 trace 的 span 可能隔几秒才到齐，也可能同时挤进来，
它们的采样结论必须一致，采就整条采，丢就整条丢。

## 实现说明

自适应路径把**决策、统计、控制**三件事拆开，互相不挡：

- 决策（每个 span 都走）：结论由 `trace_unit(trace_id) < 当前采样率`
  给出，和静态模式是同一套确定性算法。结论算一次后放进进程内的
  `DecisionCache`：16 个分片、每片“当代/旧代”两代普通 dict，trace 只在
  首次出现时在分片锁内写入，命中是无锁 dict 读；当代写满 16384 条或
  到龄 5 秒时整体换一代，旧代再活一代，没有逐条 TTL/LRU 开销。旧代
  命中说明这条 trace 还在活跃，顺手把它带回当代“续命”，避免活跃
  trace 在换代边界被丢掉后撞上变化的采样率。同一条 trace 的 span
  隔几秒到齐、或几十个同时挤进来，拿到的都是缓存里的同一个 bool；
  条目真正淘汰之后若同 trace 还有极晚到的 span，按同一个 trace_id
  和当前采样率重算，采样率未变则结论依旧一致。
- 统计（每个 span 都走）：决策结果先写进**线程本地**的 (total,
  sampled) 计数，热路径无共享锁，只有线程首次登记本地槽时短暂加一次
  锁。控制线程在 tick 时把所有线程的增量一次性 `add_many` 进滑窗。
- 控制（每 1/4 窗口时长一次）：到点的 span 线程用非阻塞抢锁，只有一个
  线程执行：先 drain 线程本地计数，再在滑窗的**同一把锁**里拍 total、
  sampled 的一致快照（旧实现分两次加锁读数，中间可能正好撞上滚桶
  清账，两个计数会读岔），折算成每秒速率喂给控制器。

阈值（采样率）怎么调，在 `RateController.observe` 里：

- 采样率直接按 `rate = target_per_sec / 吞吐` 反演：吞吐翻倍采样率
  就减半。不拿“实际采了多少条”做反馈闭环——trace 决策恒定后
  `吞吐 × 采样率` 天然等于采样条数，再反馈只会放大噪声。
- 吞吐先过一次指数平滑（EMA，每步采信 2/3 新值），窗口一格的抖动
  只被吸收一部分，流量小幅波动不会一惊一乍，峰值过后两三步就能
  沉回目标。
- 单步变化夹在 [1/4, 4] 倍内（首次观测除外），异常读数不会把采样率
  一步钉到地板或天花板；结果再夹到 `[min_rate, 1.0]`，流量低于
  target 时自然就是全采。
- 窗口空时保持当前采样率，不再有“一窗没采到就拽到 1.0”的动作；
  起步阶段窗口没攒满时按实际经过的时间（horizon）折算速率，并在
  攒够 128 条后快速先算一次，避免按满窗折算把吞吐估小一个数量级、
  采样率一步到底。

性能：8 线程压测约 50 万 span/秒（含 crc32 与缓存），相对每秒十万
span 的峰值有 4 倍以上余量。

## 运行

```bash
python3 demo.py                          # 现状演示：四个现场
python3 -m unittest discover -s tests -v # 行为基线测试
```
