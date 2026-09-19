# bucketd

网关自研的令牌桶限流模块，单进程内嵌，纯标准库，无外部依赖。

## 模块说明

`bucketd/bucket.py` 提供令牌桶 `TokenBucket(rate, burst, clock=None)`：

- `try_allow(cost=1)`：余额够扣则扣掉并返回 True，否则返回 False
- `allow(cost=1)`：语义同上，余额不足时抛 `RateLimitError`
- `available()`：当前余额（惰性补充后的值）
- 令牌按 `rate` 个/秒匀速补充，空闲时余额可一直累积到 `burst` 上限
- 扣减只发生在余额足够时，余额不会因扣减而为负

`bucketd/clock.py` 提供时钟抽象：`SystemClock` 为进程默认时钟，
`FakeClock` 支持 `advance()` / `jump_to()` 手动推进，供测试注入。

## 运行

```bash
python3 demo.py
```

## Known Issues
