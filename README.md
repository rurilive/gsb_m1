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

- `ResolverCache(upstream, clock=SystemClock(), default_ttl=30.0, *,`
  `negative_ttl=5.0, jitter=0.0, rng=None, refresh=True)`。
  前三个参数是原有对外签名，位置、名字、默认值都没动，现有调用方照旧；
  后面是本轮新增的可选关键字参数。上游对象提供 `resolve(name) -> Answer`，
  `Answer` 带 `name` / `address` / `ttl`，`ttl` 为 `None` 时用 `default_ttl`。
- `lookup(name) -> str`：命中返回地址；没命中打一次上游再返回；
  上游失败抛 `UpstreamError`，错误照原样传给调用方。
- `stats()`：`hits` / `misses` / `upstream_calls` / `errors` / `entries` 计数快照。
- `FakeUpstream.stats()` 给 `calls` 与 `peak_in_flight`，用来数上游被打了几次。

## 行为规则

- **负缓存**：上游失败按 `negative_ttl` 秒记一笔负缓存，有效期内同名
  lookup 直接抛当时那个 `UpstreamError`，不再回源；过期后重新回源。
  `negative_ttl=0` 关掉负缓存。负缓存不做后台预刷新。
- **单飞**：同一个域名的并发未命中只放一路请求回源，其余线程等这份
  结果；上游失败时错误广播给所有等待者，每个等待者都拿到同一个异常。
- **后台预刷新**：正向条目有效期过半后，第一次命中顺手起一个后台线程
  回源刷新（每条目同时只刷一路），命中线程照常返回旧值。刷新失败不再
  重试，旧值继续顶到硬过期，硬过期后按未命中重新回源。`refresh=False`
  整体关掉。
- **抖动**：所有有效期（正向、负向）落缓存前乘上 `1±jitter` 的随机因子，
  避免条目集中到期一起失效。`jitter` 取值 `[0, 1)`，默认 0（不抖）；
  随机源用 `rng` 注入（需有 `uniform(a, b)`），测试传固定种子的
  `random.Random` 即可复现。

## 边界规则

- **到点那一刻**：仍算命中。时钟读数严格大于到期时刻才算过期。
- **对时回拨**：当前读数小于此前见过的最大读数，视为时钟不可信，
  全部条目立即失效清空，从回拨后的读数重新计。
- **上游给零或负 TTL**：应答不落缓存，每次 lookup 都回源；
  `ttl=None` 仍走 `default_ttl`。

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
