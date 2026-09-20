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
- 容量满时按 LRU 顺序驱逐；内部一把锁保护，`loader` 在锁外执行
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
