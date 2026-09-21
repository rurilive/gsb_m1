# shardstore

缓存层的内存键值表，纯标准库，分片集合在建表时定死。

- `shardstore/store.py`：`ShardedKV` 的 `put()` / `get()` / `delete()` 读写，`shard_of()` 查键落在哪片，`keys_in()` / `size()` / `distribution()` / `total()` 看分布
- `tests/test_store.py`：行为基线
- `demo.py`：读写与分布演示
