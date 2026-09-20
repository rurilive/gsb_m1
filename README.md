# scheduler

告警平台内置的单进程任务调度模块。纯标准库实现，时钟通过 `Clock` 接口注入，
测试可用 `FakeClock` 手动推进时间，保证确定性。

## 快速开始

```bash
python3 demo.py                          # 起两个任务跑 6 秒的演示
python3 -m unittest discover -s tests -v # 防回归测试
```

```python
from datetime import timedelta
from scheduler import Scheduler, SystemClock, IntervalTrigger, DailyTrigger

sched = Scheduler(SystemClock(), worker_count=2, tick=1.0, misfire_grace=60.0)
sched.add("heartbeat", IntervalTrigger(timedelta(seconds=30)), fn)
sched.add("berlin-0930", DailyTrigger(9, 30, tz="Europe/Berlin"), fn)
sched.start()
```

## Known Issues

以下缺陷均已修复，并配有 `tests/test_regressions.py` 中的同名防回归测试。

- **每日任务在夏令时切换日偏移 1 小时**（`DailyTriggerDstTest`）
  现象：柏林 09:30 的巡检任务在夏令时切换当天晚 1 小时执行，次日自愈。
  根因：`DailyTrigger.next_after` 跨天时先转成 UTC 再加 24 小时；UTC+24h 在
  切换日不等于墙钟 +1 天（当天只有 23/25 小时）。
  修复：改为直接在本地墙钟时间上加 1 天，offset 由 zoneinfo 按新日期解析。

- **任务被删除/暂停后仍被执行一次**（`StaleQueueEntryTest`）
  现象：运维删掉一个任务后，它仍被执行了一次。
  根因：到期任务先进入内存队列、后由 worker 取出执行，但 worker 取出时不校验
  队列项的 `generation`，也不检查 `paused`；入队后被暂停/删除/重建的任务，其
  过期队列项仍会触发执行。
  修复：`add`/`pause`/`resume` 使 `generation` 单调递增，worker 执行前校验任务
  仍存在、未暂停且 `generation` 与入队时一致，否则丢弃；`remove` 同时清理
  `_inflight` 标记。

- **时钟前跳后过期任务疯狂补跑、轻微迟到任务不执行**（`MisfireTest`）
  现象：NTP 校时使时钟前跳后，早已过期的任务被疯狂补跑，只晚到一两分钟的
  任务反而一个都没执行。
  根因：misfire 判断写反——`late >= misfire_grace` 才入队执行（应为 `<`）；
  且 `next_run` 每拍只前进一格，过期任务在追平前被反复入队。
  修复：仅当迟到时间在宽限期内才补执行一次；无论是否补跑，`next_run` 直接
  推进到当前时刻之后的下一格，错过的周期全部折叠，不再补跑风暴。

- **31 号的月报在 2 月 28 日误触发**（`MonthlyTriggerTest`）
  现象：每月 31 号 8 点的月报任务，2 月 28 日那天也跑了。
  根因：`MonthlyTrigger.next_after` 用 `min(day, 当月最后一天)` 把日期钳制到
  月末，与 crontab 的 day-of-month 语义不符。
  修复：短月不存在该号则整月跳过，顺延到下一个存在该日的月份。

- **重启后暂停任务复活、next_run 偏 8 小时**（`StoreRoundTripTest`）
  现象：服务重启后，之前被暂停的任务自己跑起来了；有的任务下一次执行时间
  整体偏了 8 小时。
  根因：`Store` 快照根本没有写入 `paused` 字段；`next_run` 以 Asia/Hong_Kong
  本地时间去掉时区后保存，加载时却按 UTC 解析，差出 8 小时。
  修复：`paused` 一并写入快照；`next_run` 以带时区偏移的 UTC ISO8601 格式
  保存，加载时统一归一到 UTC。
