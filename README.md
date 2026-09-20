# bloomx

埋点去重用的布隆过滤器，纯标准库，容量在建实例时定死。

- `bloomx/filter.py`：`BloomFilter.add()` / `in bf` / `len(bf)` / `to_bytes()` / `from_bytes()`，按容量与目标假阳性率算位数组大小
- `tests/test_filter.py`：行为基线
- `demo.py`：写入与查询演示

## 实现说明

- `bloomx/shard.py` 的 `ShardedBloomFilter` 按片管理多个 `BloomFilter`；只追加新片，旧片冻结不改，写满当前片可自动添片或用 `add_shard()` 在线手动添片
- 添片与写入在同一把可重入锁内完成，正在写的条目始终落在确定的片上，不丢条
- 查询遍历全部片取并集：任一片命中即存在，漏查任何一片都会造成假阴性
- 整体假阳性率按各片实际置位比例合成：`1 - ∏(1 - (置位数/位数)^哈希数)`，不是各片数值的平均
- 磁盘新格式为 `BLM2`；`from_bytes()`/`load()` 自动识别老 `BLM1` 单实例文件，老片原样保留为第一片，后续按需扩容
- 内存兜底由 `max_shards` 封顶：`add_shard()` 到顶抛 `RuntimeError`；自动添片到顶后继续写活动片、不中断服务，`capped` 置位并告警一次
