# skiplist

检索侧的有序索引，纯标准库，无外部依赖。

## 现状

`skiplist/ordered.py` 提供 `OrderedMap`，排序列表加旁路字典：

- `put(key, value)`：插入或覆盖，新键返回 True、覆盖返回 False
- `get(key, default=None)`：按键查找
- `range_scan(lo, hi)`：扫描闭区间 `[lo, hi]`，返回按键升序的 `(key, value)` 列表
- `keys()` / `items()` / `first()` / `__contains__` / `__len__`

## 问题

查找靠 bisect 是 O(log n)，但 `put` 要把排序列表的后半段整体后移，是 O(n)。
键规模化之后插入是瓶颈；删除、按排名查询这些能力目前完全没有。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_ordered.py` 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```