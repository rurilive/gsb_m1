# scheduler

单进程内嵌的轻量任务调度模块，纯标准库实现。时钟通过 `Clock` 抽象注入
（线上用 `SystemClock`，测试用 `FakeClock`），支持固定间隔、每日墙钟、
每月几号三类触发器，具备 misfire 宽限、worker 池、暂停/恢复与 JSON 快照持久化。

## 快速开始

```bash
python3 demo.py
```

回归测试：

```bash
python3 -m unittest discover -s tests
```

对外 API 保持不变：`Scheduler(clock, worker_count, tick, misfire_grace, store)`，
方法 `add / remove / pause / resume / get / start / stop / save / load` 签名不变。

## Known Issues

以下五个线上反馈问题均已修复，根因与修复方式记录如下。

### 1. 柏林 09:30 巡检在夏令时切换当天晚一小时

- **根因**：`DailyTrigger.next_after` 先在带时区的 datetime 上做
  `+ timedelta(days=1)`。`zoneinfo` 的 aware datetime 做固定 24 小时加法时
  保留的是同一个固定 UTC 偏移（墙钟"跟着日期平移"），而不是重新按墙钟定位。
  春令时切换日（UTC 偏移 +1 → +2）当天 09:30 被算成了 UTC 08:30，即当地
  10:30；切换完成后再推进时偏移已恒定，序列看起来"第二天自己恢复"。
- **修复**：改为在 **naive 本地墙钟** 上推进日期、定位 `hour:minute`，
  最后再 `.replace(tzinfo=self.tz)` 附加时区转 UTC，每天都重新解释墙钟。
  秋令时回拨日（25 小时）行为也在回归测试中覆盖。

### 2. 任务删除后仍被执行了一次

- **根因**：到期任务先入 `queue.Queue`，`remove` 只从任务表里摘除；worker
  滞后取到队列里的旧条目时，仅凭 task id 查表（此时为 `None` 能挡住一部分，
  但"删除后用同 id 重新添加"的场景会误命中新任务），且 `pause` 后已在途的
  条目同样没有失效机制。
- **修复**：调度器维护单调递增的代际（generation），队列条目携带入队时的
  代际；`add / pause / resume / load` 都会分配新代际。worker 执行前比对当前
  任务的代际，不一致即丢弃。删除后残留的旧条目永远不会再执行，同 id 重建
  也不会被旧条目命中。

### 3. 时钟前跳后过期任务疯狂补跑、晚到一两分钟的任务反而不执行

- **根因**：`_loop` 的 misfire 判断条件写反了——`late >= misfire_grace`
  才入队，导致宽限期内的正常迟到任务被静默丢弃；而对远超宽限的任务，每个
  tick 只把 `next_run` 向 `trigger.next_after(next_run)` 推一个网格，于是
  NTP 前跳后每个 tick 都补跑一次历史锚点，形成补跑风暴。
- **修复**：改为 `late <= misfire_grace` 才执行；无论执行与否，到期任务都
  用 `trigger.next_after(now)` 一步合并（coalesce）到当前时刻之后的下一个
  锚点，错过的多次触发只保留未来的一次，tick 再密也不会翻历史账。

### 4. 每月 31 号的月报在 2 月 28 号执行

- **根因**：`MonthlyTrigger.next_after` 用 `day = min(self.day, last)`，
  把"该月没有 31 号则整月跳过"的 crontab 语义写成了"退到当月最后一天"，
  于是 2 月落在 28/29 号、小月落在 30 号。
- **修复**：当 `self.day > 当月最后一天` 时跳过整个候选月继续找，直到落在
  真正拥有该日期的月份（1/3/5/7/8/10/12 月）才产生触发点。

### 5. 重启后暂停任务自己跑起来；部分任务 next_run 整体偏 8 小时

- **根因**：`Store.save` 根本没有持久化 `paused`，加载时默认 `False`，
  暂停状态在重启后丢失；同时 `next_run` 被转成 `Asia/Hong_Kong` 墙钟后
  抹掉 tzinfo 落盘，`load` 却把这个裸时间直接当作 UTC，读回的时刻比实际
  晚 8 小时（东八区偏移）。
- **修复**：快照保存完整的 `paused` 字段；`next_run` 统一以带时区的 UTC
  ISO 字符串落盘和读取。对旧版本写出的香港墙钟裸时间快照做兼容：加载时按
  `Asia/Hong_Kong` 解读再转 UTC，老快照恢复后不再偏移。
