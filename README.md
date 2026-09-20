# tsdb

监控后端的内存时序库，纯标准库。

- `tsdb/store.py`：`TimeSeriesStore`，写入 (timestamp, value) 点，按闭区间查询原始点
- `tsdb/rollup.py`：`RollupStore`，降采样归档层，按范围自动选择精度层
- `tests/test_store.py`：行为基线
- `tests/test_rollup.py`：归档行为基线
- `demo.py`：写入与区间查询演示

## 实现说明

- 窗口按纪元对齐：`w = (ts // 精度) * 精度`，与窗口内第一条点无关，同一分钟不会被切成两段。
- 每个桶只存可增量合并的聚合态（sum/count/min/max），不常驻原始点。
- `archive(cutoff)` 把 `ts < cutoff` 的原始点并入各层后立即丢弃；重跑时原始点已不在，天然幂等，均值不会翻倍。
- 迟到点（ts 早于归档水位线）直接并入对应桶的聚合态，不会丢失，日结能对上。
- 查询按范围选层：取满足 `范围 // 精度 >= min_buckets` 的最粗层；更小的范围回原始点。
- 归档层只取完整落在查询区间内的窗口；尚未归档的新点以原始精度拼在结果尾部。
