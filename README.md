# bloomx

埋点去重用的布隆过滤器，纯标准库，容量在建实例时定死。

- `bloomx/filter.py`：`BloomFilter.add()` / `in bf` / `len(bf)` / `to_bytes()` / `from_bytes()`，按容量与目标假阳性率算位数组大小
- `tests/test_filter.py`：行为基线
- `demo.py`：写入与查询演示

## 实现说明

- 分片管理：`ScalableBloomFilter`（`bloomx/shard.py`）持有一串 `BloomFilter` 片，只写最后一片，写满就在线追加新片，旧片只读不搬数据、不停机
- 新片容量按 `growth` 放大，目标假阳性率按 `ratio` 递减，几何级数求和保证整体不超 `fp_rate`
- 查询：逐片检查，任一片命中即算写过，不漏片就不会有假阴性
- 整体假阳性率：`overall_fp_rate = 1 - ∏(1 - p_i)`，`p_i` 按各片实际写入量估算，对外只报这一个数
- 并发：`add` 全程持锁，添片与写入同一把锁，扩容期间不丢写
- 持久化：新格式 `BLM2` 存全局参数 + 每片元数据与 `BLM1` 负载；读到老 `BLM1` 文件按单片加载，容量由位数组尺寸反推，可继续添片
- 内存兜底：`max_shards` 限制片数，到顶还写满就抛 `OverflowError`
