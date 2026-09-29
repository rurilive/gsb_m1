# timewheel

纯标准库的定时器包，无外部依赖。

## 现状

`timewheel/wheel.py` 提供最朴素的定时器 `SimpleTimer`：

- `SimpleTimer()`：时钟从零起步，一拍即一个整数时刻
- `add_at(delay, name)`：把到期时刻记为时钟加延迟并追加到表尾
- `advance(n)`：把时钟推进 n 拍，返回本次触发的名字列表，已到期的按到期
  时刻与插入序触发并移除
- `peek()`：返回下一个到期时刻，无任务时返回约定值 `None`
- `cancel(name)`：线性找到并移除未到期任务，找不到返回 `False`
- `TimerError`：定时器错误基类（继承 `ValueError`）

内部就是一个列表，每次推进都要从头到尾线性扫描全部任务找到期项，
没有分层轮、没有槽位定向、没有跨级级联重排。

## 问题

每推进一拍都要扫全部任务，任务一多就白扫。推进开销随任务总量线性上涨，
与真正到期的任务量无关。

## 目标

把 `SimpleTimer` 从线性表扩成以分层时间轮为核心的调度工具，见任务描述。
约束：

- 现有行为与 `tests/test_wheel.py` 基线保持一致（基线一个字不改且全绿）
- 新行为另开 `tests/test_timer.py`
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
