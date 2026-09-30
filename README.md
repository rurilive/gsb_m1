# digitcount

区间按位计数工具，纯标准库，无外部依赖。

## 现状

digitcount/count.py 提供 IntervalCounter，统计闭区间 [low, high] 内满足数字
条件的整数个数：

- set_range(low, high)：设定并校验当前区间，下界不得大于上界、端点必须是不
  小于零的整数、上界位数不超过 MAX_DIGITS
- count_without_digit(digit, low, high)：不含给定数字的数的个数
- count_digit_sum(target, low, high)：各位数字之和恰为给定值的数的个数
- count_strict_increasing(low, high)：相邻两位严格递增的数的个数
- count_multiple(base, low, high)：为给定数之整数倍的数的个数
- find_minimum(condition, arg, low, high)：区间内满足条件的最小整数，无解
  返回 None
- independent_enumerate 与 independent_minimum：两条独立慢速做法，与主路径
  逐项对账
- range_width / digits / enumerate_visits / digit_visits / state_visits：
  区间宽度、上界位数与上一次计算的计数，数位状态访问次数基线恒为零
- Erro：异常基类，下分 RangeErro、ValueErro 与 ParamErro

每条计数都从区间下界逐个枚举到上界，对每个整数取出各位再逐条判定，区间一大
就慢，但结果正确。

## 问题

逐数枚举对每个整数逐位检查条件，判定次数与区间长度线性相关，区间每放大十倍
就多走十倍的路；多次查询互不复用，同一个前缀被反复重数；求最小具体数同样是
从下界线性扫到上界。四条能力共用一条枚举核心，拿不出任何计数说明更聪明的
做法省了多少，也没有把区间拆成不超过上界的计数再端点相减的手段。下界为零、
下界等于上界、区间只含一位数、上界为全九、不含某数字与全部数字都含、数字和
为零、相邻递增在一位数上平凡成立、倍数为一这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_count.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
