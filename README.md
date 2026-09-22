# nestrun

基于事件循环的轻量任务调度器，纯标准库，无外部依赖。任务可以派生子任务、
带延迟开工、带总预算超时，可以整棵取消。时间从注入的时钟读，定时全挂在
事件循环的堆上，不用线程。

## 现状

`nestrun/scheduler.py` 提供 `Scheduler`，任务对象在 `nestrun/task.py`：

- `Scheduler(clock=time.monotonic)`：clock 为注入时钟，测试和演示里用 `nestrun.ManualClock`
- `Scheduler.submit(name, body, *, delay=0.0, timeout=None, on_done=None)`：
  提交根任务，body 是任务体，签名为 `body(task)`，返回 `Task`
- `Scheduler.run(block=False)`：把当前能处理的事件处理完，返回事件数
- `Task.spawn(name, body, *, delay=0.0, timeout=None, on_done=None)`：
  在任务体里派生一个子任务
- `Task.cancel(reason="cancelled")`：请求取消
- `Task.add_done_callback(callback)`：挂一个落定回调
- 任务状态：pending / running / succeeded / failed / cancelled，`task.history` 记录走过的状态
- `task.error`：失败时是任务体抛出的异常，取消时是 `Cancelled`（带 reason）
- `Scheduler.armed_timers()`：还挂着、没有被撤销的定时器数量

## 语义约定

- `timeout` 是从提交时刻算起的总预算，到点还没落定就按超时判取消；`delay` 只影响开工时刻
- 任务体返回后若还有子任务没落定，任务保持 running，等子任务都落定再收尾
- 收尾时汇总子任务的结果：任一子任务失败，本任务就以它的错误失败（派生顺序里第一个失败的）；
  否则只要有子任务被取消，本任务也取消；否则成功
- 取消沿派生关系传播，整棵子树一起落定；已经落定的任务不受取消影响
- 每个任务无论走成功、失败还是取消，落定回调合计恰好触发一次；落定之后再挂的回调立即触发一次
- 所有状态变化都要经过 `check_transition` 校验，非法转换抛 `InvalidTransition`，
  合法转换表见 `nestrun.LEGAL_TRANSITIONS`

## 问题

多层编排接进来之后，值班连着撞上几类怪事：取消父任务时，已经派生出去的子任务照跑，
最后父任务自己还翻回成功，落定回调被叫了两次；子任务失败或取消之后，父任务永远停在
running 没人收尾；被取消过的任务状态还会被改写，超时点过后有它名下的定时器跑出来，
取消原因也被 timeout 盖掉。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_scheduler.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 单层与嵌套派生的对照现场
python3 -m unittest discover -s tests -v # 行为基线测试
```
