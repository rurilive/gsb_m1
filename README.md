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

## 测试报告

测试位于 `tests/test_timewheel.py`（标准库 unittest，注入 `ManualClock` 定死时序，
对拍使用固定 seed，可独立重复运行）：`python3 -m unittest discover -s tests`。
共 19 个用例：13 绿、6 红。红用例与对应缺陷如下（每个红用例上方注释写有
「README 期望什么 / 实际发生什么」）：

- `test_last_slot_participates_in_wraparound`、`test_full_revolution_delay_not_fired_early`
  —— 缺陷：`add` 落槽取模误用 `slots - 1`，最后一个槽（下标 slots-1）从不参与
  回绕，任务被错放槽位，导致到期不触发或整圈任务第一个 tick 就被提前触发；
  修复方向：落槽改为 `(self._cursor + steps) % self._slots`。
- `test_same_delay_adds_two_distinct_tasks` —— 缺陷：就绪队列用 deadline 作 dict
  key，相同 deadline 的任务互相覆盖丢失；修复方向：就绪队列改用列表按追加
  顺序保存（或以 (deadline, 序号) 作 key）。
- `test_cancel_ready_task` —— 缺陷：`cancel` 只查找槽位，已进入就绪队列但尚未
  被 `due()` 取走的任务无法取消（返回 False 且仍被取出）；修复方向：`cancel`
  同时检查就绪队列并移除其中的任务。
- `test_wrapping_multi_slot_advance_fires_crossed_slots` —— 缺陷：`advance` 回绕
  分支第二段 `range(0, new_cursor)` 漏掉着陆槽（与落槽缺陷叠加后任务丢失/
  迟到）；修复方向：回绕时把着陆槽也包含进来（`range(0, new_cursor + 1)`）。
- `test_fuzz_against_reference` —— 对拍红：固定 seed 随机交错 挂载/取消/推进/
  取走共 400 步，与朴素参考实现（按到期时刻排序、推进时扫描到期项）对比，
  触发序列与 cancel 返回值不一致，是上述缺陷在随机序列下的综合表现。

其余 README 语义均为绿：参数校验（delay≤0、超一整圈、时间回退）、亚 tick
不推进、整 tick 步进、due 按到期先后且清空、句柄彼此独立、槽内取消幂等、
取走后取消返回 False、推进不改变已挂任务到期时刻、小步推进=大步推进、
迟到不豁免。`timewheel/` 与 `demo.py` 未做任何改动，`python3 demo.py` 照常运行。
