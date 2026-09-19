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

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## Known Issues

以下四个线上事故现象已修复，根因与修复方式如下（防回归测试见 `tests/`）：

1. **NTP 校时时钟回拨期间限流形同虚设**
   根因：`_refill` 在 `elapsed < 0`（时钟回拨）时直接把余额重置为
   `burst` 满桶，回拨瞬间白送一整桶配额，请求全部放行。
   修复：时钟回拨（或没有前进）时不补充任何令牌，也不回拨内部时间戳
   `_last`，墙钟追平后按真实流逝时间继续补充。

2. **桶被打空后长时间无法恢复、持续全拒**
   根因：`try_allow` 的「检查余额」与「扣减」分属两个锁临界区
   （check-then-act），并发下余额被扣成负数；之后补充要从负值
   慢慢爬回 0，表现为远超预期时间的全拒。
   修复：检查与扣减合并到同一把锁的临界区内，余额不再可能为负，
   空桶按 `rate` 正常恢复。

3. **压测偶发放行数超过桶内余额**
   根因：与现象 2 同一处竞态——多个线程同时通过余额检查后各自
   扣减，导致同一瞬间放行数超过实际余额。
   修复：同上，检查与扣减原子化后，任何时刻放行总量不超过
   补充总量与余额之和。

4. **低速率大桶（burst=1000）余额攒不到配额上限**
   根因：补充上限被错误地钳到 `rate`（`_capacity = self.rate`）
   而非 `burst`，burst 大于 rate 时余额永远超不过 rate。
   修复：补充上限改为 `burst`，空闲累积可到配额上限。
