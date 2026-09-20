# sfcache

带单飞（singleflight）合并的缓存加载器，单进程内嵌，纯标准库，无外部依赖。

## 模块说明

`sfcache/cache.py` 提供 `Cache(loader, ttl=None, clock=time.monotonic)`：

- `get(key)`：命中且未过期直接返回；否则调用 `loader(key)` 回源，
  把结果写入缓存后返回
- 同一个 key 上并发到达的请求合并成一次回源，共享同一份结果
- `ttl`：条目存活秒数；`None` 表示永不过期
- `invalidate(key)`：删除该 key 的缓存条目，并清除它的失败标记
- `loads`：累计回源次数
- `clock`：时间读取统一走它，便于测试注入

`loader` 由调用方提供，签名 `loader(key) -> value`；抛异常表示回源失败。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues
