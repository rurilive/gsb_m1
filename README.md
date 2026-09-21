# geogrid

本地经纬度点位索引，纯标准库，无第三方依赖。

## 现状

- `geogrid/geo.py`：坐标校验、经度归一（180 折到 -180）与 `haversine_m` 球面距离
- `geogrid/cells.py`：固定边长格网切分，`cell_of(lat, lon, cell_deg)` 给出 `(row, col)`
- `geogrid/index.py`：`PointIndex`，`add` 登记、`remove` 摘除、`at` 精确坐标查询、`scan` 全量遍历、`stats` 状态快照；id 为任意可哈希对象，查询结果按登记顺序返回

数据都是普通浮点，不引入任何坐标系转换。

## 目标

见任务描述。约束：纯标准库，`tests/` 基线保持全绿。

## 运行

```bash
python3 demo.py                           # 精确查询与遍历演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```
