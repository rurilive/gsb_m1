# btreelab

检索侧的有序索引，纯标准库，无外部依赖。

## 现状

`btreelab/index.py` 提供 `SortedList`，一个有序列表维护的键值映射：

- `put(key, value)`：插入或覆盖，新键返回 True、覆盖返回 False
- `get(key, default=None)`：按键查找
- `delete(key)`：按键删除，删到返回 True、不存在返回 False
- `range_query(lo, hi)`：扫描闭区间 `[lo, hi]`，返回按键升序的 `(key, value)` 列表
- `keys()` / `items()` / `first()` / `__contains__` / `__len__`

插入时线性找到位置再把后半段整体后移，按区间查询时从起点线性扫描到终点。
没有任何树结构，没有节点，没有分裂合并。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_index.py` 基线保持一致（基线一字不改，必须全绿）
- 纯标准库，全部能力仍在 `btreelab` 包内

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
