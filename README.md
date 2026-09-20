# guardcache

规则服务的进程内多级缓存，命中直接用，未命中回源加载，纯标准库，无外部依赖。

## 模块说明

`guardcache/cache.py` 提供 `GuardCache(loader, ttl=None, capacity=128,
negative_ttl=30, hot_capacity=None, clock=time.monotonic)`：

- 两级结构：热层（`hot_capacity`，默认与 `capacity` 相同）与主层（`capacity`）。
  命中主层会提升到热层，两层共享同一条记录，存活时刻始终一致
- `get(key)`：命中缓存直接返回；未命中调用 `loader(key)` 回填后返回
- `loader` 由调用方提供，签名 `loader(key) -> value`；抛 `NotFound` 表示 key
  不存在，缓存据此记入负缓存，`get` 随之抛出 `NotFound`
- `ttl`：正条目存活秒数，`None` 表示永不过期
- `negative_ttl`：负条目存活秒数，`None` 表示永不过期
- `invalidate(key)`：删除该 key 的正/负缓存条目，返回是否真的删掉了
- 容量满时按 LRU 顺序驱逐；负条目有独立的容量池（与主层同大小），不会
  被正常条目挤掉；内部一把锁保护，`loader` 在锁外执行
- `clock`：时间读取统一走它，便于测试注入

## 计数器

`stats()` 返回计数快照，每次调用返回新 dict：

- `hits`：读取被缓存直接满足的次数（正、负条目都算）
- `misses`：需要回源处理的读取次数
- `loads`：实际调用 `loader` 的次数
- `evicted`：因容量被驱逐的条目数
- `negatives`：写入的负条目数

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

以下四条为已修复问题，记录现象、根因与修法：

1. **回源异常后 key 一直拿到空结果**：`loader` 抛出非 `NotFound` 异常时，
   旧实现把 `None` 当正常值写进缓存，且按正条目 TTL 存活（`ttl=None` 时
   永不过期），上游只抖了一下，这些 key 却再也好不了，只能重启进程。
   修法：异常占位条目改用短时效（`_ERROR_TTL = 1s`），既在下游故障期间
   挡住同一 key 的重复回源，又让 key 到期后自动重试、快速自愈。
2. **热门 key 并发未命中，旧快照覆盖新值**：同一 key 并发未命中时每个
   线程各自回源，最慢的 loader 最后写缓存，把它带回的旧快照盖在新值上。
   修法：引入 singleflight（`_inflight`），同一 key 同一时间只允许一个
   在途回源，其余请求等它完成后直接读缓存结果，不再重复回源，也就不存
   在旧值覆盖新值。
3. **热 key 命中即续期，TTL 形同虚设**：`get` 命中时把 `expires_at` 重置
   为当前时刻 + TTL，被读个不停的 key 永远不过期，上游改了也不生效。
   修法：命中不再续期，过期时间只在写入时确定，到期必回源。
4. **负条目被容量挤掉，不存在的 key 打爆下游**：负条目与正常条目共用主
   层容量池，缓存一满占位就先被 LRU 挤走。修法：负条目改用独立容量池
   （`_neg`，与主层同大小、独立 LRU），正常条目再多也挤不掉它们。
