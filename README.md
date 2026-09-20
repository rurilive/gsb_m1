# tsdb

监控后端的内存时序库，纯标准库。

- `tsdb/store.py`：`TimeSeriesStore`，写入 (timestamp, value) 点，按闭区间查询原始点
- `tests/test_store.py`：行为基线
- `demo.py`：写入与区间查询演示

## 实现说明

- 窗口按绝对边界对齐：起点 = `ts - ts % window`，与首点到达时间无关，同一窗口的数据不会被切成两段。
- 归档层每窗口只存 `(count, total, min, max)` 一条聚合，内存占用与点数解耦，可长期驻留。
- `archive(before)` 把窗口右端 `<= before` 的原始点并入归档层后从原始层删除，过期原始点安全丢弃。
- 重跑幂等：已归档的点不在原始层，重复执行 `archive` 找不到点，不会重复计数。
- 迟到点：归档后才到的点仍留在原始层，下次 `archive` 按同一窗口起点并入聚合，不会丢失。
- 精度层选择：`query_auto` 在跨度 `>= 2 * window` 时走归档层（窗口均值），否则回原始点；也可直接调 `query` / `query_rollup`。
