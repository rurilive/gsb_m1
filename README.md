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

- 管线分三层：`registry.py` 把计数器/直方图状态收进实例并给原始视图，`snapshot.py` 把口径（排序/求和/最近秩分位）算成不可变快照，`render.py` 三个纯函数消费同一份快照，`meters.py` 的模块函数只做薄壳转发。
- 导出不再各抄一份：排序、求和、分位只在 `snapshot.py` 实现一次；渲染层只管字段序与排版，JSON 的 count 在前、prom 的 quantile 在前仅是渲染差异，统计口径完全一致。
- 快照是冻结 dataclass、不含任何格式化，统计口径可直接对 `percentile`/`histogram_snapshot` 独立单测。
- 标签接入点：`Registry` 以 `(name, labels)` 为键登记，快照条目携带 labels 透传，三个 renderer 只改名字串接即可；对外函数签名与字节输出保持不变。
