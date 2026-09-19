# idemkit

任务提交处理包，单进程内嵌，纯标准库，无外部依赖。

## 现状

`idemkit/dispatcher.py` 提供 `Dispatcher`：`register(task_name, fn)` 注册处理器，`dispatch(task_name, payload)` 同步执行一次并返回结果。

约定：

- handler 签名 `fn(payload)`，抛出的异常原样上抛
- 结果必须能通过 JSON 往返（`json.dumps` 后 `json.loads` 与原值相等），元组、自定义对象等会被 `NotSerializableError` 拒绝

行为以 `tests/test_dispatcher.py` 为准。

## 问题

上游调度器是至少一次投递语义，网络抖动就会把同一个任务重复提交过来。现在每次 dispatch 都会真实执行一遍：重复提交一次就多跑一次，费时任务白白消耗资源，下游计数也对不上。

## 目标

见任务描述。约束：

- `Dispatcher` 现有行为保持不变（`tests/test_dispatcher.py` 是行为基线，一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
