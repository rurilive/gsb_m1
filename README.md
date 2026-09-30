# halfenum

一个纯标准库的子集搜索工具包，无外部依赖。背包预估、凑数选款、对账凑单这类
场景都要在整数集合上找子集，halfenum 就是干这件事的那一层。

## 现状

- `halfenum/naive.py`：位掩码全枚举实现。`iter_subsets(values)` 从 0 枚举到
  2 的 n 次方减一，逐个产出升序下标元组。
- `max_subset_sum(values, capacity)`：不超过容量上限的最大子集和，空集和为 0。
- `subset_sum_solution(values, target)`：恰好凑成目标值的方案，多解取下标序列
  字典序最小的一条，凑不出返回 None。
- `count_achievable_sums(values)`：所有子集能得到多少个不同的和值。
- `group_difference(values, mode)`：把集合均分成两组，求和之差绝对值的最小或最大。
- 入参校验：元素必须是整数，布尔与浮点拒收；错误基类 `HalfEnumError`，
  `InvalidInput` 表示入参非法。

现有实现每个能力都老老实实枚举全部子集，n 一大枚举量就是 2 的 n 次方。
`naive_enumeration_count(n)` 只是把这层规模摊开给人看，并不改变枚举本身。

## 问题

`subset_sum_solution` 多解时要在全枚举里反复比较下标序列，`max_subset_sum`
也要把每个子集的和算一遍。n 到二十几，两百万到上千万个子集，凑数选款这种
要反复问的场景就卡死了。`group_difference` 同样靠位掩码切分，逃不掉指数。

## 目标

见任务描述。约束：

- `tests/test_naive.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库，异常统一继承 `HalfEnumError`
- 同一批数据在新老两条路径上逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
