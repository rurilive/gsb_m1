# tickbox

纯标准库的定时器包，无外部依赖。

## 现状

`tickbox/timers.py` 提供最朴素的定时器集合 `TimerSet`：

- `TimerSet(clock=None)`：clock 可注入，默认 `time.monotonic`
- `add(delay, payload=None, priority=0)`：挂 delay 秒后触发的定时器，返回句柄，delay 需为正
- `tick(now)`：把时钟推进到 now，取走所有 `deadline <= now` 的到期句柄
- `cancel(handle)`：取消定时器，已取消或已触发的返回 `False`
- `now`、`size`：当前时钟与待触发定时器数
- `TimerError`：定时器错误基类（继承 `ValueError`）

内部就是一个列表，每次 tick 从头到尾线性扫描找 deadline 到点的定时器，
没有分层轮、没有取消的常数级定位、没有跨级级联。

## 目标

把 `TimerSet` 从线性扫描改成分层时间轮，见任务描述。约束：

- 现有行为与 `tests/test_timers.py` 基线保持一致（基线一个字不改且全绿）
- 新行为另开 `tests/test_wheel.py`
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
