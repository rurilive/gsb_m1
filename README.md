# sfcache

带单飞（singleflight）合并的缓存加载器，单进程内嵌，纯标准库，无外部依赖。

## 模块说明

`sfcache/cache.py` 提供 `Cache(loader, ttl=None, clock=time.monotonic)`：

- `get(key)`：命中且未过期直接返回；否则调用 `loader(key)` 回源，
  把结果写入缓存后返回
- 同一个 key 上并发到达的请求合并成一次回源，共享同一份结果
- `ttl`：条目存活秒数；`None` 表示永不过期
- `invalidate(key)`：删除该 key 的缓存条目（回源失败不写缓存，无失败标记可清）
- `loads`：累计回源次数
- `clock`：时间读取统一走它，便于测试注入

`loader` 由调用方提供，签名 `loader(key) -> value`；抛异常表示回源失败。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

以下问题均已修复（修复前的现象 → 根因 → 修复方式）：

1. **回源超时一次后，该 key 此后一直报同一个错，只能重启恢复。**
   - 根因：旧实现在回源失败时把异常永久写进 `_failed`，且 `get` 入口
     无条件优先抛出 `_failed` 里的异常；`_failed` 永远不会被清理
     （`invalidate` 也只删 `_data`）。于是一次瞬时抖动被固化成该 key 的
     永久失败，且后续根本不再回源。
   - 修复：删除整个 `_failed` 机制。回源失败不落任何缓存，只通知当趟
     参与者，下一次 `get` 自然重新回源。

2. **一批请求永久不返回，卡住数量正好等于该 key 当时的并发数。**
   - 根因：`_fail` 只写了 `_failed` 和 `flight.error`，既没有从
     `_flights` 摘除这趟 flight，也没有 `flight.done.set()`。同一趟上
     等待的跟随者全部永久阻塞，每个占住一个工作线程，表现为线程池
     被占满、后续请求排队。
   - 修复：`_fail` 现在在锁内摘除自己这趟 flight（以 flight 身份比对，
     防止误删新一轮回源），先发布 `flight.error` 再 `flight.done.set()`
     唤醒全部等待者；等待者收到异常后正常返回，后续请求可重新回源。

3. **热门 key 高峰期回源次数翻几倍，且少数请求拿到的不是本轮结果。**
   这一现象由两个独立缺陷叠加：
   - 根因一（回源翻倍）：条目过期走的是单独分支，只在栈上 new 了一个
     `_Flight` 却没注册进 `_flights`，于是过期 key 上每个并发请求都
     自认为 leader、各自回源一次，单飞在过期场景完全失效；且过期旧值
     一直留在 `_data`，新结果晚到的并发请求会读到上一轮的旧值。
   - 根因二（结果错配）：`_finish` 的发布顺序是先 `flight.done.set()`
     唤醒跟随者、之后才写 `flight.value` 和缓存。跟随者可能在信号置位
     与结果写入之间醒来，读到尚未发布的 `None`；多趟回源并存时还会拿到
     别的轮次写入的旧值。
   - 修复：未命中与过期统一为一条路径——leader 在锁内创建并注册 flight、
     同时摘除过期条目，跟随者一律挂到当趟 flight 上；`_finish` 改为先写
     `flight.value`、再在锁内更新 `_data`/计数，最后才 `done.set()`。
     这样同一 key 同一时刻只有一次回源，且信号发布时本轮结果已可见。

对应防回归测试见 `tests/test_regression.py`。
