# crawlkit

抓取队列的 URL 去重层，纯标准库，无外部依赖。调度器入队前问 `DedupStore` 这条
URL 是不是重复，抓过的记下来，避免同一页面反复抓。

## 现状

- `crawlkit/hashing.py`：哈希原语。`digest()` 是加固定盐的 sha256，`hash_pair()`
  劈出两个 64 位无符号数，`bit_indexes()` 做双重哈希展开，`bucket_index()` 折桶，
  `fingerprint()` 取固定位数指纹（恒不为零）。
- `crawlkit/bloom.py`：`BloomFilter(capacity, fp_rate=0.01)`。`add(key)` 置位，
  `key in bf` 查询，`len(bf)` 是加键次数，`stats()` 出计数快照，
  `to_bytes()` / `from_bytes()` 落盘读回。
- `crawlkit/cuckoo.py`：`CuckooFilter(capacity, fp_bits=12)`。接口与布隆对齐，
  外加 `remove(key)` 真删；踢出链超限自动翻倍扩容重排，全程迭代，已加未删
  的键永远命中。
- `crawlkit/store.py`：`DedupStore(capacity, fp_rate=0.01, backend="bloom")` 门面。
  `mark(key)` 记录已入队，`is_duplicate(key)` 判重，`retry(key)` 撤销（cuckoo
  后端真删，bloom 后端抛 `NotSupportedError`），`stats()` 出统计，同样有
  `to_bytes()` / `from_bytes()`。
- `crawlkit/errors.py`：`NotSupportedError`。

位数组只置位不清位，所以布隆过滤器只加不删；布谷鸟过滤器存指纹，可删。
判重只会多报不会漏报。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
