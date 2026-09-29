# cuckoof

去重层的过滤器组件，纯标准库，无外部依赖。

## 现状

- `cuckoof/naive.py`：`NaiveSet(capacity)`，基于 dict 的朴素集合。
  `add(key)` 登记并返回是否新键，`key in s` 判定命中，`remove(key)`
  删一个键并返回是否删到，`stats()` 出计数快照，`len(s)` 数成员。
- `cuckoof/hashing.py`：`digest()` 加固定盐的 sha256，`hash_pair()`
  劈出两个 64 位无符号数，`fingerprint(key, bits)` 取指定位宽指纹，
  `two_indexes(fp, h1, h2, num_buckets)` 由指纹与哈希数算两个候选桶。
- `cuckoof/randomstate.py`：`RandomState(seed)` 定种随机流，`below()`
  取范围内整数，`shuffle()` 就地打乱，`fork()` 派生子流。
- `cuckoof/errors.py`：`CuckooError` 与 `CapacityError`。

朴素集合判定精确、不产生假阳性，但成员判定本身没有省内存的路子，
键一多 dict 就跟着涨；也没有指纹桶、没有扩容，规模上来只能靠调用方
自己兜着。

## 问题

去重层要能扛住远超名义容量的键量，还要能安全地撤回。当前实现既没有
指纹桶带来的空间压缩，也没有可删除、误判有界、能扩容的过滤结构。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
