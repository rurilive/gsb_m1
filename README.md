# tsdb

监控后端的内存时序库，纯标准库。

- `tsdb/store.py`：`TimeSeriesStore`，写入 (timestamp, value) 点，按闭区间查询原始点
- `tests/test_store.py`：行为基线
- `demo.py`：写入与区间查询演示
