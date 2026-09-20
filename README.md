# scheduler

单进程内嵌的轻量任务调度模块，纯标准库实现。时钟通过 `Clock` 抽象注入
（`SystemClock` / `FakeClock`），支持固定间隔、每日（带时区）、每月触发器，
内置 misfire 宽限、worker 池、任务增删/暂停恢复与 JSON 快照持久化。

## 快速开始

```bash
python3 demo.py                 # 注册两个任务跑 6 秒，确认模块可用
python3 -m unittest discover -s tests -v
```

```python
from datetime import timedelta
from scheduler import Scheduler, SystemClock, IntervalTrigger, DailyTrigger

sched = Scheduler(SystemClock(), worker_count=2, tick=1.0, misfire_grace=60.0)
sched.add("heartbeat", IntervalTrigger(timedelta(seconds=30)), fn)
sched.add("berlin-0930", DailyTrigger(9, 30, tz="Europe/Berlin"), fn)
sched.start()
```

对外 API（`add` / `remove` / `pause` / `resume` / `get` / `start` / `stop` /
`save` / `load` / `wait_idle` / `wait_queue_len`）及 `demo.py` 行为保持不变。

## Known Issues（已修复）

以下五个线上现象的根因均已修复，并由 `tests/` 下的回归测试覆盖。

### 1. 柏林 09:30 巡检在夏令时切换当天晚一小时、次日自愈

根因：`DailyTrigger.next_after` 推进日期时先转成 UTC 再加
`timedelta(days=1)`（固定 24 小时）。春季跳变日柏林 UTC 偏移从 +01:00
变为 +02:00，多加的 24 小时换算回墙钟就成了 10:30；偏移稳定后第二天
自然恢复正常。修复：一律在**本地墙钟**上按日历日推进，再通过 PEP 495
规则转 UTC——春季不存在的时刻（gap）顺延到间隙结束，秋季歧义时刻
（fold）取第一次出现。

### 2. 任务删除后仍被执行一次

根因：worker 只凭队列里的 `task_id` 查任务表，完全不比对入队时携带的
`generation`；删除（或暂停）前已经入队的陈旧条目会照常调用任务函数
（同名任务重新 `add` 后甚至会命中新任务）。修复：`generation` 改为
调度器级单调递增，`add/remove/pause/resume` 都会换代号；worker 执行前
校验「任务仍存在、generation 一致、未暂停」，陈旧条目直接丢弃。

### 3. NTP 时钟前跳后过期任务疯狂补跑、晚一两分钟的反而不执行

根因：到期收集里的 misfire 判断条件写反了——`late >= misfire_grace`
时才入队，于是只晚 1~2 分钟（小于宽限期）的任务被静默跳过；同时
`next_run` 每次只推进一格，时钟前跳后循环会把所有历史槽位逐个
「补跑」入队。修复：改为 `late <= misfire_grace` 才补跑（宽限期内每次
扫描最多入队一次）；超过宽限期的历史槽位视为 misfire 直接丢弃，
`next_run` 一次性推进到当前时刻之后的下一个槽位，杜绝补跑风暴。

### 4. 每月 31 号的月报在 2 月 28 号执行

根因：`MonthlyTrigger.next_after` 用 `min(day, monthrange)` 把目标日
钳到当月最后一天，31 号在短月被悄悄改写成 28/30 号，与「短月整月跳过」
的 crontab 语义相悖。修复：当月不存在目标日时整月跳过，继续找下一个
存在该日的月份。

### 5. 重启后暂停的任务自己跑起来，部分任务下次执行时间偏 8 小时

根因在持久化的两处缺陷：

- `Store.save` 把 `next_run` 转成 `Asia/Hong_Kong` 墙钟后**剥掉
  tzinfo** 存成裸时间，`load` 却把裸时间按 **UTC** 解释，整体偏差正好
  8 小时。修复：统一以带偏移的 UTC ISO-8601 存取；加载旧格式裸时间时
  按香港时区解释以兼容历史快照。
- 快照没有保存 `paused`，`load` 重建的任务恒为未暂停，重启即恢复运行。
  修复：持久化 `paused` 并在加载时还原。

此外，`resume` 现在会把暂停期间已过期的 `next_run` 重新排到当前时刻
之后（错过的槽位不补跑），语义与 `add` 一致。
