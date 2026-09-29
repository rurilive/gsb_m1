# dsulib

连通集合工具，纯标准库，无外部依赖。

## 现状

`dsulib/union.py` 提供 `Recompute`：

- `add(x)`：加入一个此前不存在的元素，自成单元素集合
- `union(a, b)`：合并 a、b 所在的两个集合，返回合并后集合大小
- `connected(a, b)`：判断两元素是否同属一个集合
- `component_size(x)`：x 所在集合的元素个数
- `count_components()`：遍历统计当前不同集合的个数
- `members(x)`：返回 x 所在集合全部元素的拷贝

内部只维护一张 元素 -> 所属集合 的映射，每个集合是一个 Python 集合。
合并时线性地重建集合，查询按当前映射逐次核算，因此规模一大就慢。
查询不存在的元素、或重复加入已存在的元素，抛 `ValueError`。

## 问题

合并与查询都是线性代价，分量计数每次全量遍历；没有带权（相对势）概念，
也无法把已经做过的合并撤销回去。这些能力目前都缺。

## 目标

见任务描述。约束：

- `tests/test_union.py` 是行为基线，一个字不许改，必须原样全绿
- 新行为另开 `tests/test_dsu.py`，用固定序列与逐字断言
- 纯标准库

## 运行

```bash
python3 demo.py                           # 连通集合现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

（实现后补，10 行以内）
