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
- `stats()`：`hits` / `misses` / `upstream_calls` / `errors` / `entries` 计数快照。
- `FakeUpstream.stats()` 给 `calls` 与 `peak_in_flight`，用来数上游被打了几次。

## 现状

过期判断只有读路径上的一次比较，边界没写死；上游失败不落任何记录；
同一个域名并发到达时各查各的；TTL 原样使用，没有额外的有效期策略。

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
