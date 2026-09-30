# knapsackdp

纯标准库的背包问题小工具，无外部依赖。

## 现状

`knapsackdp/knapsack.py` 提供一份朴素实现 `NaiveKnapsack`：

- `__init__(weights, values, capacity)`：物品重量、价值与容量上限，非法参数抛出 `KnapsackError`
- `__len__()`：物品个数
- `capacity`：容量上限
- `max_value()`：递归枚举每个物品取或不取，返回最大总价值
- `count_combinations()`：枚举取或不取，统计可行的装载组合个数
- `KnapsackError`：参数错误的基类，继承 `Exception`

## 问题

`max_value` 与 `count_combinations` 都是对每个物品做取或不取的递归枚举，
逐条累加重量判断是否超限，结果是正确的，但代价随物品个数指数级上涨；
既没有二维或滚动数组的动态规划路径，也没有零一背包与完全背包、
恰好装满等口径的区分，规模一上来就撑不住。

## 目标

见任务描述。约束：

- `tests/test_knapsack.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_dp.py`
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
