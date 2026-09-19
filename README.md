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

以下缺陷已于本轮修复，对应回归测试见 `tests/test_bucketd.py`：

1. **NTP 校时回拨期间限流形同虚设**：根因有二。其一，`_refill` 对
   `elapsed < 0` 的处理是把余额直接重置为 `burst` 且不更新基准时间，
   回拨期间每次检查都白送满桶；其二，`SystemClock` 使用墙钟
   `time.time()`，NTP 校时直接作用于限流。修复：回拨时不补充、不重置，
   仅把基准时间钳到当前时刻，待时钟追平后恢复匀速补充；
   `SystemClock` 改用单调时钟 `time.monotonic()`，不受墙钟回拨影响。
2. **桶打空后无法恢复（低速率桶永久全拒）**：根因是桶容量被错误地
   初始化为 `rate` 而非 `burst`（`self._capacity = self.rate`）。
   当 `rate < 1` 时余额上限不足 1 个令牌，`cost=1` 的请求永远被拒绝。
   修复：`_capacity` 改为 `burst`。
3. **压测偶发放行超预算**：根因是 `try_allow` 的"检查余额"与"扣减"
   分两次取锁，check-then-act 之间存在竞态，多线程可同时通过检查再
   各自扣减，使放行数超过余额。修复：补充、检查、扣减合并到同一把锁
   内原子完成。
4. **低速率大桶（burst=1000）余额攒不到上限**：与现象 2 同根因——
   补充上限被钳到 `rate` 而非 `burst`，空闲再久余额也超不过 `rate`。
   修复后余额可正常累积到 `burst` 上限。
