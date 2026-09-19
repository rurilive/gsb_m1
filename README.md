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

以下问题均已修复，防回归测试见 `tests/`（`python3 -m unittest discover -s tests`）：

- **NTP 校时时钟回拨，限流形同虚设（已修复）**：根因有二。其一，
  `SystemClock` 使用墙钟 `time.time()`，NTP 回拨会直接体现为时间倒流；
  其二，`_refill` 对 `elapsed < 0` 的处理是把余额直接重置为 `burst`，
  回拨瞬间白送一整桶。修复：`SystemClock` 改用单调时钟
  `time.monotonic()`（免疫校时回拨）；`_refill` 对 `elapsed <= 0`
  直接忽略，不补充、不重置、不推进基准时间，时钟追平后按真实
  净流逝时间统一结算。
- **桶被打空后无法恢复、请求持续全拒（已修复）**：根因是构造时
  `self._capacity = self.rate`，补充上限被错写成速率而非 `burst`。
  当 `rate < 1`（如 0.5/s）时余额上限不足 1 个令牌，`cost=1` 的请求
  永远放行不了。修复：容量上限改为 `burst`。
- **压测偶发放行超预算（已修复）**：根因是 `try_allow` 的
  检查（`_affords`）与扣减（`_deduct`）分两次加锁，存在
  check-then-act 竞态：多个线程可同时通过余额检查再各自扣减，
  余额被扣成负数，放行数超过实际余额。修复：检查与扣减合并为
  同一次持锁内的原子操作。
- **低速率大桶（burst=1000）余额攒不到配额上限（已修复）**：与
  第二条同根因——容量上限被错设为 `rate`，空闲再久余额也被钳在
  速率值上，到不了 `burst`。修复后空闲累积以 `burst` 为上限。
