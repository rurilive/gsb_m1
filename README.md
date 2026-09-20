# bloomx

埋点去重用的布隆过滤器，纯标准库，容量在建实例时定死。

- `bloomx/filter.py`：`BloomFilter.add()` / `in bf` / `len(bf)` / `to_bytes()` / `from_bytes()`，按容量与目标假阳性率算位数组大小
- `tests/test_filter.py`：行为基线
- `demo.py`：写入与查询演示
