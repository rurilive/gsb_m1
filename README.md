# intervaldp

区间划分与括号匹配工具包，纯标准库，无外部依赖。

## 现状

intervaldp/interval.py 提供 IntervalKit：

- merge_cost(stones, cost_each, lo, hi)：把一段石子合并成一堆的最小代价，可指定子区间
- best_split(stones, cost_each)：把整段切成两段的最优分裂点，并列取最小
- longest_valid(text)：最长合法括号子串的长度，无合法子串返回零
- min_add(text)：使整串合法所需添加的最少括号数，按区间枚举分裂点求最优
- split_visits：本次调用朴素枚举的分裂点次数
- char_visits：本次调用括号判定逐字符扫描次数
- IntervalErro：异常基类，下分 TextErro、StoneErro、CostErro

## 问题

合并代价对每个区间枚举全部分裂点，且每次把左右两半的代价重新递归算一遍，
不做任何缓存，长度一长就是立方甚至更高量级。最优划分沿用同一套枚举。括号
匹配对每个子串都从头用栈重新扫，全部子串枚举下来是平方量级。四条路都慢，
也拿不出任何计数说明更聪明的做法省了多少，边界情形更无从对照。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_interval.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
