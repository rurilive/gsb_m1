# metrics

进程内指标注册表，纯标准库。

- `metrics/registry.py`：`Registry` 注册 counter/gauge，标签维度分序列，`snapshot()` 导出
- `tests/test_registry.py`：行为基线
- `demo.py`：注册与导出演示
