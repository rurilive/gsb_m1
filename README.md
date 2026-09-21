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

## 实现说明（自适应模式）

决策与统计彻底分开：`should_sample` 只负责"这条 trace 采不采"和记账，采样率
由 `RateController` 在独立的控制步上根据 `SlidingWindow` 的快照推进。静态
模式一行逻辑没动。

### 决策怎么定：trace 级确定性 + 结论钉住

- 每条 trace 用 `trace_unit(trace_id)`（crc32 归一化到 [0,1)，不依赖
  PYTHONHASHSEED）跟当前采样率比较拍板，结论天生确定性，进程间一致。
- 自适应模式的采样率会随时间变，仅靠 `unit < rate` 无法保证同一条 trace
  的多个 span 结论一致（rate 一变结论就可能翻转）。因此用一份 `_DecisionCache`
  把每条 trace 第一次拍板的结论钉住：span 隔几秒才到齐也好、几十个同时挤
  进来也好，都复用同一个结论。缓存命中只续期、不重新拍板。
- 缓存 32 分片，各片独立锁；每片按插入顺序保存，TTL（8 秒）+ 容量
  （4096 条/片）双保险。淘汰只从队首弹：过期算惰性清理、没过期算 FIFO，
  全部摊销 O(1)——不做周期性全表扫描，避免十几万条目时周期性卡顿。

### 阈值怎么调：只看总吞吐，平滑 + 死区 + 限幅

- `SlidingWindow` 是真正的分桶滑动窗口：桶只在它对应的时间段彻底滑出
  窗口时才清，跨桶边界计数不归零（旧实现一滚格就清空全部桶，统计周期性
  塌到 0，控制器读数跟着跳）。
- total 和 sampled 用 `add_many` 一次写入同一桶、`rates()` 一次读同一批
  桶的快照，两个计数不会读岔（旧实现两次独立加锁读写，压测里把阈值一步
  拽到底就是读岔造成的）。
- 控制步每 1/4 窗口走一次，用**非阻塞抢锁**，抢不到说明别的线程已经调
  过，决策线程不等这把锁。启动后 50ms 先走第一步，避免按初始 1.0 超采
  一整秒。
- 期望率 `desired = min(1, target / total_per_sec)`，流量低于目标直接顶
  1.0 全采。决策**只看 total**：sampled 仅留作对账，不再参与阈值计算，
  从根上消除两个计数读岔把阈值带飞的可能。
- 调节三道保险：EMA 平滑（α=0.6）压小波动；5% 死区（拿**期望值**与当前
  率比，不能拿平滑候选值比，否则会渐近但永远够不着目标）让稳态不乱动；
  单步变化限幅 10 倍，脏读数也不会一步砸到 min_rate。`sampled=0` 不再
  触发"砸 1.0"，无流量时维持现状。
- 重新切入 adaptive 时窗口、控制器、钉过的结论全部 reset，互不串账。
