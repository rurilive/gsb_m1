# metrics

进程内指标注册表，纯标准库。

- `metrics/registry.py`：`Registry` 注册 counter/gauge，标签维度分序列，`snapshot()` 导出
- `tests/test_registry.py`：行为基线
- `demo.py`：注册与导出演示

## 实现说明

- 超限降级：单指标序列数达 `max_series` 后，新维度不拒写、不丢数据，并入 `__overflow__` 兜底桶，看板不断
- 按指标限：`max_series` 挂在每个指标上（注册表可给默认值，注册时可覆盖），A 爆不影响 B
- 观测：快照带 `cardinality` 段——上限、当前序列数、兜底桶是否启用、被打掉的总写入数与维度样本（有界 128 条）
- 恢复：`reset()` 让序列数回落后，被打掉的维度下次写入自动恢复为独立序列；兜底桶旧值保留不并回
- 导出约束：`snapshot(series_budget=N)` 限制单次导出总序列数，超出截断并标 `truncated`，防止全量序列化顶爆内存
