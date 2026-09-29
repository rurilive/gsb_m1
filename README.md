# bloomx

埋点管线的去重层，纯标准库，无外部依赖。管线在入库前问一句这个事件是不是
重复的，不重复才往下走，避免同一事件被反复处理。

## 现状

- `bloomx/hashing.py`：哈希原语与定容换算。`digest()` 是加固定盐的 sha256，
  `hash_pair()` 劈出两个 64 位无符号数（可选盐区分不同层的展开），
  `bit_indexes()` 做双重哈希展开，`sizing()` 按容量与目标误判率算位数与哈希个数。
- `bloomx/randomstate.py`：`RandomState(seed)` 定种随机流。`getrandbits()` 取整数，
  `below()` 取范围内整数，`salt()` 取非零 64 位盐，`fork()` 派生子流。
- `bloomx/bloom.py`：`BloomFilter(capacity, fp_rate=0.01)`。`add(key)` 置位，
  `key in bf` 查询，`stats()` 出计数快照，`to_bytes()` / `from_bytes()` 落盘读回，
  `remove()` 抛 `NotSupportedError`。
- `bloomx/errors.py`：`NotSupportedError` 与 `CapacityError`。

位数组只置位不清位，所以布隆过滤器只加不删；判重只会多报不会漏报。

## 问题

只加不删意味着撤下来的事件永远被误判成重复；定容一层装满了要么超载要么
整段重建，容量没有弹性；也没有误判率的量化出口，调参靠猜。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
