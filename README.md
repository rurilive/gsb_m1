# scheduler

告警平台任务调度模块：单进程内嵌运行，时钟注入（`Clock`/`FakeClock`/`SystemClock`），纯标准库实现。

## 快速开始

```bash
python3 demo.py
```

## 测试

```bash
python3 -m unittest discover -s tests -t .
```

## 模块说明

- `scheduler/clock.py`：时钟抽象，所有时间读取与等待都走注入的 `Clock`。
- `scheduler/triggers.py`：触发器（`IntervalTrigger`/`DailyTrigger`/`MonthlyTrigger`），决定下一次触发时刻（UTC）。
- `scheduler/scheduler.py`：调度器主体，到期收集、misfire 控制、worker 池、增删暂停恢复。
- `scheduler/store.py`：任务表 JSON 快照持久化，保存 `next_run` 与 `paused`，供进程重启恢复。

## Known Issues

以下问题已在 2026-09-21 的修复中解决，附根因说明：

- **柏林 09:30 巡检任务在夏令时切换日晚 1 小时（次日自愈）**
  根因：`DailyTrigger.next_after` 计算"下一天"时先把候选时刻转成 UTC 再加 24 小时，
  跨夏令时切换时偏移量变化导致墙钟时刻漂移 1 小时。修复：直接在本地墙钟上加一天
  （zoneinfo 感知型 datetime 的算术保持墙钟语义），再换算回 UTC。

- **任务被删除（或暂停）后仍被执行一次**
  根因：调度循环入队时携带了 `generation`，但 worker 取出后将其丢弃（`_gen`），
  既不校验代数也不校验 `paused`，导致入队后发生的删除/暂停无法拦截已入队的触发。
  修复：worker 执行前校验任务仍存在、未暂停且 `generation` 与入队时一致；
  `remove` 同时清理 `_inflight` 残留。

- **时钟前跳（NTP 校时）后过期任务疯狂补跑，晚到一两分钟的任务反而不执行**
  根因：misfire 判断写反——`late >= misfire_grace` 才入队，导致准点/稍晚到的任务
  永不执行，而严重过期的任务每 tick 入队一次；且 `next_run` 只按原网格逐格推进，
  时钟前跳后逐格追赶形成补跑风暴。修复：改为 `late <= misfire_grace` 才执行
  （超出宽限的 misfire 直接跳过不补跑），并将 `next_run` 重锚到 `now` 之后的
  下一个触发点，杜绝追赶。

- **每月 31 号的月报任务在 2 月 28 日误跑**
  根因：`MonthlyTrigger.next_after` 用 `min(day, 当月最后一天)` 钳位日期，
  31 号在短月被钳到 28/30 号触发。修复：短月不存在该号时整月跳过（与 crontab
  day-of-month 语义一致），顺延到下一个存在该日的月份。

- **重启后被暂停的任务自己跑起来、部分任务 next_run 整体偏 8 小时**
  根因：`Store.save` 未持久化 `paused` 字段；且 `next_run` 先转成香港本地墙钟再
  剥离时区信息写入，加载时却被当作 UTC 解析，产生 8 小时偏差。修复：快照以带
  时区偏移的 UTC ISO 格式保存 `next_run`，并持久化/恢复 `paused`。
