# metrics

进程内指标注册表，纯标准库。

- `metrics/registry.py`：`Registry` 注册 counter/gauge，标签维度分序列，`snapshot()` 导出
- `tests/test_registry.py`：行为基线
- `demo.py`：注册与导出演示

## 实现说明

- 降级：超限只丢新序列，已有序列照常写入；被丢写入并入 `__overflow__` 兜底桶，看板总量不断
- 限额按指标各自生效：`Registry(max_series=)` 设全局默认，`counter/gauge(..., max_series=)` 单指标覆盖，A 爆不连累 B
- 观测：snapshot 每个指标带 `cardinality`（上限、活跃序列数、被丢写入次数、被丢维度采样），采样上限 128 条防止观测数据自身撑爆内存
- 恢复：`reset()` 清空序列与溢出状态，被丢维度下次写入即回正常序列、从零起算，兜底桶历史随 reset 清零
- 导出：每指标序列数封顶 `max_series + 1`（含兜底桶），全量序列化体积随之有界
