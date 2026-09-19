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

## 幂等语义

`idemkit/idempotent.py` 提供 `IdempotentSubmitter(dispatcher, store_dir, ttl, clock=time.time)`，在 `Dispatcher` 前加幂等键层：

- `submit(idem_key, task_name, payload)`：同键 TTL 内重复提交直接返回首跑结果，handler 不再执行
- 结果连同键与到期时间落 `store_dir` 下的 JSON 文件（每键一文件，原子替换），进程重启后同键从文件重放
- 并发同键只执行一次：按键加锁 + 双查，其余线程等首跑结果
- 过期条目惰性清理：读写时顺手删，不起后台线程
- `clock` 可注入，测试拨快时钟即可验证过期重跑
