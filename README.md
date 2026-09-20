# sfcache

带单飞（singleflight）合并的缓存加载器，单进程内嵌，纯标准库，无外部依赖。

## 模块说明

`sfcache/cache.py` 提供 `Cache(loader, ttl=None, clock=time.monotonic)`：

- `get(key)`：命中且未过期直接返回；否则调用 `loader(key)` 回源，
  把结果写入缓存后返回
- 同一个 key 上并发到达的请求合并成一次回源，共享同一份结果
- `ttl`：条目存活秒数；`None` 表示永不过期
- `invalidate(key)`：删除该 key 的缓存条目
- `loads`：累计回源次数
- `clock`：时间读取统一走它，便于测试注入

`loader` 由调用方提供，签名 `loader(key) -> value`；抛异常表示回源失败。
回源失败不会被缓存：本次合并的调用方收到异常，下一个请求会重新回源。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

（已修复，见下）历史上三个线上现象，根因都在 `sfcache/cache.py` 的
并发路径上，已一并修复并补充防回归测试 `tests/test_regression.py`：

- **某个 key 回源超时一次后持续报错，重启才恢复**
  根因：`_fail` 把异常写入 `_failed[key]`，`get` 入口无条件重抛，
  失败被永久"缓存"，且 `invalidate` 并未清除该标记。
  修复：失败不再落盘到任何 per-key 状态，异常只传给本次合并的
  调用方，下一个请求正常重新回源。
- **一批请求不返回，线程池被占满，数量恰为该 key 的并发数**
  根因：`_fail` 既没有 `flight.done.set()` 也没有把 flight 从
  `_flights` 摘除，所有跟随者永远阻塞在 `done.wait()` 上。
  修复：失败路径在锁内摘除 flight、记录异常并放行所有等待者。
- **热门 key 回源次数翻倍，且同批请求拿到的值不一致**
  根因有二：其一，条目过期分支新建 `_Flight` 却不注册进 `_flights`，
  并发请求各自成为 leader 重复回源；其二，`_finish` 在锁外先
  `done.set()` 再写 `_data`、最后才赋 `flight.value`，既留出
  "既无缓存又无 flight"的窗口让新请求再次回源，又让被唤醒的
  跟随者读到赋值前的 `None`。
  修复：过期条目走统一的合并路径（flight 一定注册进 `_flights`）；
  `_finish`/`_fail` 全程在锁内按"写结果 → 摘 flight → 放行"的
  顺序完成，跟随者拿到的必然是本轮加载的结果。
