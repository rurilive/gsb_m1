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

以下四个线上问题已修复（修复于 bucketd/bucket.py），并补充 tests/ 防回归测试：

1. **NTP 回拨时钟后限流形同虚设**
   根因：`_refill()` 在 `elapsed < 0`（时钟回拨）时直接把余额重置为 `burst`，
   回拨期间每次取令牌都先白送一整桶，请求全部放行。
   修复：时钟回拨时跳过本次补充、不改动余额，且不回退 `_last`，
   墙钟追回后回拨区间也不会被重复计息。

2. **桶被打空后永远缓不过来**
   根因：容量上限被错配为 `self._capacity = self.rate`，余额最多只能攒到
   rate；凡是单次 cost 大于 rate 的请求，在桶打空后永远凑不够余额，表现为全拒。
   修复：容量上限改为 `burst`。

3. **压测偶发放行超预算**
   根因：`try_allow()` 的"检查余额"（`_affords`）和"扣减"（`_deduct`）是两段
   独立的临界区，并发下多个线程可同时通过检查再各自扣减，导致同一瞬间放行数
   超过余额（check-then-act 竞态）。
   修复：检查与扣减合并到同一把锁内原子完成。

4. **低速率大桶（burst=1000）余额攒不到上限**
   根因：同问题 2，容量被钳制在 rate，空闲再久余额也顶不到 burst。
   修复：同问题 2，容量上限改为 `burst`。

## 测试

```bash
python3 -m unittest discover -s tests -v
```
