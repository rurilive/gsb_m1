# resolvcache

接入层用的进程内解析缓存，纯标准库，对外没引任何三方依赖。
生产里接真实解析服务，测试、演示和对拍都注入假上游和手动时钟。

## 结构

```
resolvcache/clock.py     系统时钟与可手动推进的注入时钟
resolvcache/upstream.py  假解析上游（内存 zone、调用计数、失败标记）
resolvcache/cache.py     ResolverCache
resolvcache/refcheck.py  跟直连上游的随机请求对拍
demo.py                  演示脚本
tests/                   行为测试
```

## 用法

```python
from resolvcache.cache import ResolverCache
from resolvcache.clock import ManualClock          # 生产不传 clock
from resolvcache.upstream import FakeUpstream

upstream = FakeUpstream({"a.svc.internal": ("10.0.0.1", 20.0)})
clock = ManualClock(0.0)
cache = ResolverCache(upstream, clock=clock, default_ttl=30.0)
cache.lookup("a.svc.internal")   # 未命中打上游，返回地址并记进缓存
cache.lookup("a.svc.internal")   # 未过期，直接返回
```

- `ResolverCache(upstream, clock=SystemClock(), default_ttl=30.0)`，
  上游对象提供 `resolve(name) -> Answer`，`Answer` 带 `name` / `address` / `ttl`，
  `ttl` 为 `None` 时用 `default_ttl`。
- `lookup(name) -> str`：命中返回地址；没命中打一次上游再返回；
  上游失败抛 `UpstreamError`，错误照原样传给调用方。
- `stats()`：`hits` / `misses` / `upstream_calls` / `errors` / `entries`
  计数快照，另有 `refreshing` 表示在飞的后台预刷新数量。
- `FakeUpstream.stats()` 给 `calls` 与 `peak_in_flight`，用来数上游被打了几次。

## 有效期策略

构造时还有三个只靠关键字传的可选项，老调用方不用动：

```python
ResolverCache(upstream, clock=SystemClock(), default_ttl=30.0,
              *, negative_ttl=5.0, jitter=0.1, rng=None)
```

- `negative_ttl`：上游失败的负缓存有效期（秒），和正缓存分开配。
- `jitter`：有效期抖动比例，取值 `0.0~1.0`；实际 TTL 在
  `ttl*(1±jitter)` 区间均匀取值，避免一批条目同时到期；`0.0` 关闭抖动。
- `rng`：抖动随机源，接受 `random.Random` 同接口对象，默认新建一个；
  测试里注入固定种子（如 `random.Random(123)`）结果完全可复现。

### 正缓存：半程预刷新，失败顶旧值

每条成功应答记正缓存，带两个时刻：

- `soft_at = 存入时刻 + TTL/2`：进入软过期。`lookup` 立即返回旧地址，
  同时只放一个后台请求预刷新；软过期窗口内的后续请求继续拿旧值，
  不重复放刷新。
- `expires_at = 存入时刻 + TTL`：硬过期。此时的 `lookup` 同步等结果，
  有在飞的刷新就并入那一份，没有就自己打一次上游。

后台预刷新失败时，旧正缓存原样留到 `expires_at`（软窗口内不再补刷，
避免上游抖动时在旧值窗口里反复回源）；到硬过期仍失败才抛错。

### 负缓存：失败也记一笔

上游抛 `UpstreamError` 时，按 `negative_ttl` 记一条负缓存（同样叠加抖动）。
有效期内再查同一名字，直接把上次的错抛给调用方，不打上游。负缓存没有
旧值可顶，不做半程预刷新，到期即重新回源。非 `UpstreamError` 异常不落负缓存。

### single-flight：同一名字只放一个请求

同一个名字的并发 `lookup`（缓存为空、硬过期、或预刷新已在飞）只允许一个
请求到上游，其余线程在事件上等这一份结果：成功都拿到同一地址，上游失败
则同一个异常实例广播给所有等待者。`FakeUpstream.stats()["peak_in_flight"]`
可以验证同一时刻在飞请求数始终为 1。

## 边界规则（测试锁定）

- **到点那一刻**：有效期判定用 `now >= expires_at`，正缓存、负缓存都一样。
  即 `now == expires_at` 的那一查算硬过期：正缓存并入/发起一次回源，
  负缓存重新打上游；半程点 `now == soft_at` 同样算进入软过期。
- **对时回拨**：缓存不维护独立时间，一切以注入时钟的读数为准。时钟回拨后
  按新读数重判，旧条目可能重新变新鲜；回拨不删条目、不补 TTL，到期时刻
  保持不变，再拨回去照样在原时刻过期。
- **上游给零 TTL**：`ttl=0`（含 `default_ttl=0` 兜底、或 `negative_ttl=0`）
  表示"这次结果不落缓存"：条目不写入字典，下一个请求照常回源；但并发到达
  的同一批请求仍由 single-flight 合并成一次上游调用。

## 约束

- `tests/` 里的既有测试是对外行为的基线，保持原样全绿。
- `resolvcache/refcheck.py` 的随机对拍是验收门槛：返回逐条跟直连一致，
  缓存的上游调用数不超过直连的 `RATIO_BOUND` 倍（默认 0.6）。
- 新增能力仍然只依赖标准库，时钟与上游继续保持可注入。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
