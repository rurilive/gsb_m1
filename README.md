# lruvault

采集服务的进程内 LRU 缓存，纯标准库，无外部依赖。容量满时淘汰最久未用
的键，读命中会把键挪到最新，读写路径都记在计数里；上个月接入多线程网关
时给它加了一把锁，网关那边几十个工作线程共用同一个实例。

## 用法

```python
from lruvault import LRUCache

evicted = []
cache = LRUCache(capacity=1024, on_evict=lambda k, v: evicted.append((k, v)))

cache.put("user:7", payload)
payload = cache.get("user:7")            # 命中就挪到最新，不命中给 None
cache.get("user:7", fallback)            # 不命中给 fallback
cache.delete("user:7")                   # True 表示真删到了

cache.size()                             # 当前键数
cache.keys()                             # 从新到旧列键
cache.snapshot()                         # 从新到旧列 (key, value)，不动次序
cache.stats()                            # hits/misses/evictions/puts/deletes/live
cache.hit_rate()                         # hits / (hits + misses)
```

- `LRUCache(capacity, on_evict=None)`
  - `capacity`：容量上限，至少为 1
  - `on_evict(key, value)`：容量淘汰时同步调用一次，拿到被淘汰键淘汰前的
    值；`delete` 主动删除不触发回调；把这个回调抛出的异常照抛给调用方
- `key` 和 `value` 都不许是 `None`，传了就 `ValueError`
- 计数口径：`hits`/`misses` 只数 `get` 的结果，`put` 覆盖已有键不算命中；
  `puts` 数 `put` 调用次数，`deletes` 数真删掉的次数

## 目录

- `lruvault/cache.py`：`LRUCache`，服务在用的那个
- `lruvault/nodes.py`：`Node` 与 `OrderList`，缓存本体的链表结构
- `lruvault/stats.py`：计数口径与命中率
- `lruvault/reference.py`：没加锁的单线程实现 `PlainLRU`，另有
  `random_ops`/`apply_ops` 两个造操作序列、回放序列的小工具；只给对拍
  判定用，线上路径别依赖它
- `tests/`：现有行为基线

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests     # 行为基线测试
```
