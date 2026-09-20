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

- 分两层：`retrykit/core.py` 只有参数校验和唯一的重试执行循环 `_run()`；`retrykit/strategies.py` 是策略层，每个策略对象只负责 `wait(attempt)`（第 n 次失败后等多久）和 `now()`（预算判断用的时钟）。
- 内置策略经 `make_strategy()` 按名字构造：`FixedStrategy` / `ExpoStrategy` / `JitterStrategy`（jitter 复用 expo 的上限再均匀取值）。
- 执行循环不认识具体策略，只面向 `wait`/`now` 接口编程；`sleep` 和时钟均可注入（默认真实 `time.sleep`），单测不用再打补丁。
- 自定义退避曲线因此接得住：把任意 `curve(attempt)` 函数用 `CallableStrategy` 一包（或自备同接口对象）交给 `_run()` 即可，循环零改动。
