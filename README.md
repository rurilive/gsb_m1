# resilkit

可失败调用的重试执行器，纯标准库，无外部依赖。

## 现状

resilkit/executor.py 提供 Executor：

- Executor(retries=0, clock=time.monotonic, sleep=time.sleep)：retries 是除首次外的额外重试次数，clock 与 sleep 均可注入
- run(fn, *args, **kwargs)：执行 fn，失败则重试，某次成功立即返回其结果；重试与首次合计 retries + 1 次尝试
- 全部尝试都失败时抛 RetryExhausted，其 attempts 为总尝试次数，last 为最后一次的原始异常
- run_or_none(...)：同上，但耗尽时返回 None
- RetryExhausted：携带 attempts 与 last 的异常类型

## 问题

退避策略只有立即重试，没有等待与抖动，失败风暴会同步压向下游；
任何异常都被重试，不可重试的异常白白耗掉重试额度；
没有熔断，下游持续故障时调用方仍一次次打过去，缺少快速失败与自愈。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_executor.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```