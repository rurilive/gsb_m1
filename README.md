# retrykit

任务队列的重试兜底层，2018 年上线。纯标准库，无外部依赖。

## 对外 API

- `retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None, timeout=None, retry_on=(Exception,), on_retry=None)`
  - `attempts`：总尝试次数（含首次），小于 1 抛 ValueError
  - `strategy`：`"fixed"` 固定间隔 / `"expo"` 指数退避（第 n 次失败后等待 `delay * 2**(n-1)`）/ `"jitter"` 在 `[0, 同 expo 的上限]` 内均匀取值；其他值抛 ValueError
  - `max_delay`：expo/jitter 单次等待上限，None 不设上限
  - `timeout`：整个调用的时间预算（秒），某次失败后已超预算则立刻放弃，错误文本与重试耗尽不同
  - `retry_on`：可重试异常类元组，不在里面的异常原样抛出
  - `on_retry(attempt, exc, wait)`：即将重试前回调，attempt 从 1 计；最后一次失败不回调
- 放弃时抛 `RetryError`，成功时原样返回 fn 的返回值（falsy 也算成功）

行为细节（等待序列、预算边界、回调时序、错误文本）以 `tests/test_backoff.py` 为准。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- `retrykit/core.py`：单一重试循环 `RetryExecutor`，只负责执行、异常判定、时间预算、回调时序；`sleep` 与时钟可注入，默认 `time.sleep`/`time.monotonic`，行为不变。
- `retrykit/strategies.py`：策略层，`Backoff` 基类加内置 `FixedBackoff`/`ExpoBackoff`/`JitterBackoff`，只回答"第 n 次失败等多久"。
- 接入方式：`retry(strategy=...)` 可传 `Backoff` 子类实例，或直接传 `attempt -> seconds` 可调用对象作为自定义退避曲线。
- 接得住的原因：循环与等待曲线彻底解耦，新增曲线不改循环、预算和回调，旧三个策略只是同一接口的实现。
