# metrio

进程内指标收集包：计数器 + 直方图，三种文本格式导出。2019 年上线，纯标准库，无外部依赖。

## 对外 API（不可变更）

- `inc(name, n=1) -> int`：计数器加 n（n 可为负），返回加完的值
- `counter_value(name, default=0)`：读计数器，未注册返回 default
- `histogram(name)`：注册一个空直方图
- `observe(name, value)`：记样本，未注册会顺手注册
- `render_text() -> str`：人读格式；空注册表返回空串
- `export_json() -> str`：JSON，histogram 字段序 name,count,sum,avg,min,max,p50,p95,p999
- `export_prom() -> str`：prom 风格，quantile 行在前、_count/_sum 在后；空直方图无 quantile 行
- `reset()`：清空全部指标

导出格式（含字段顺序）是稳定契约，下游按字段序解析。分位数口径（最近秩法）与各边界行为以 `tests/test_meters.py` 为准。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 注册表收进 `Registry` 实例（`meters.py`），模块级函数是默认实例 `_DEFAULT` 的薄壳转发；`REGISTRY` 仍是同一 dict 的兼容别名。
- 统计口径只有一份：`Registry.snapshot()` 排序样本、算分位（`_percentile` 最近秩法）与 min/max/avg，产出不可变 `Snapshot`。
- 三种导出是「快照 → 渲染」：`_render_text/_render_json/_render_prom` 各自只拼字段，不再各抄一份统计逻辑，字段序契约集中在渲染层。
- 统计口径可脱离格式化单测：直接构造 `Registry` 实例调 `snapshot()` 断言 `HistogramStats` 字段。
- 标签维度接入点：在 `Registry` 的采集方法上加 labels 并作为注册键的一部分，快照按 (name, labels) 聚合，渲染层按既有字段序输出。
