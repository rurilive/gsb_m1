# catalanx

卡特兰数与合法括号序列的朴素求解器，纯标准库，无外部依赖。

## 现状

`catalanx/core.py` 提供 `Catalanx`：

- `catalan_recursive(n)`：第 n 个卡特兰数，用求和形式的递推式，对每个下标把两侧的卡特兰数各自递归展开，重复子问题被反复计算，并把递归展开次数与递归访问次数分别记到 `recursion_steps` 与 `recurrence_visits`
- `is_valid(s)`：判断括号串是否合法，用一个栈逐字符模拟
- `valid_prefix_count(s)`：合法前缀计数，对每个前缀单独重判一遍
- `enumerate_all(n)`：长度为 2n 的全部括号串逐条生成后逐个判合法，返回合法序列，并把全枚举条数记到 `full_enumeration_count`
- `count_sequences(n)`：长度为 2n 的合法序列条数，先把候选全部枚举再计数
- `count_monotone_paths(n)`：网格上每步向右或向上且始终不越界的路径条数，同样靠全枚举加判定
- `list_sequence(n, k)`：按字典序取第 k 个合法序列，先枚举全部再排序后取下标
- `rank_sequence(s)`：一个合法序列的字典序名次，先枚举同长度的全部合法序列再数位置

异常基类是 `CatalanxError`，参数类型不对抛 `TypeMismatchError`，括号串含别的字符抛
`InvalidBracketError`，序号或名次越界抛 `OutOfRangeError`。全部路径结果确定，但求卡特
兰数是指数量级、枚举是二的次方量级。

## 问题

求第 n 个卡特兰数的递归展开重复了大量子问题，稍大就退化成指数级；枚举合法序列先把
二的 2n 次方条候选全部生成再过滤，规模一大就卡死；判断合法性与合法前缀计数都建立在
逐字符栈模拟之上，前缀计数还对每个前缀重判；按字典序取第几个与求名次同样先枚举全部
再排序取值；也没有任何计数能把递归展开次数、递推访问次数、全枚举条数与剪枝生成条数
摆在一起对照。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改，须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
