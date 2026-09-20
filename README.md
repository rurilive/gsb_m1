# timewheel

采集 agent 里的定时任务轮：任务按延时挂进环形槽位，时间由调用方手动推进，
到期任务收集进就绪队列，由调用方取出执行（轮子本身不执行任务）。纯标准库；
起始时刻从注入的 clock 取（默认 time.monotonic，测试/演示可用
timewheel.clock.ManualClock 手动拨动）。

## 语义约定（以下为本模块的正式行为定义）

1. **时间模型与回绕定义**
   - 轮子有 slots 个槽、固定步长 tick；内部时刻 now 从 clock() 初始化，
     之后只随 advance(now) 以整 tick 步进
   - add(delay, task)：delay 必须 > 0（否则 ValueError），且不得超过一整圈
     slots * tick（否则 ValueError）；deadline = 当前 now + delay，任务放入
     槽 (cursor + ceil(delay/tick)) mod slots
   - 索引以 slots 为模，**最后一个槽（下标 slots-1）照常参与回绕**
2. **advance(now) 与迟到 tick 语义**
   - now 小于当前时刻 → ValueError；与当前时刻之差不足一个 tick → 不推进
   - 推进时逐槽前进：每跨过一个槽，就把该槽内全部任务按加入顺序追加进就绪队列
   - **一次 advance 跨多个槽（含跨回绕点）时，被跨过的每个槽的任务都必须
     恰好进入就绪队列一次，不提前、不丢失、不重复**；deadline 已过的任务
     照常触发（迟到不豁免）
3. **due()**：返回就绪队列全部任务并清空，顺序与追加顺序一致（即到期先后）
4. **去重边界**：add 返回的句柄彼此独立；**相同 delay 的两次 add 是两个
   不同任务，到期都必须出现**，不因同槽或同 deadline 而合并/覆盖
5. **取消语义**：cancel(handle) 让任务不再执行——**无论它还在槽中，还是
   已进入就绪队列但尚未被 due() 取走**；本次调用完成取消返回 True；句柄
   已取消过、或任务已被 due() 取走时返回 False（幂等，不抛错）

## 运行

```bash
python3 demo.py
```
