# subfam

连续子段统计工具包，纯标准库，无外部依赖。

## 现状

subfam/stats.py 提供 SubarrayStats：

- best_sum(seq)：最大子段和，返回 SumReport，含最优值与左右下标，空序列最优值取零、下标为负一
- bounded_sum(seq, bound)：长度不超过上界的子段中最大的和，上界为零时只允许空段
- at_most_sum(seq, bound)：和不超过上界的子段中最大的和，无解时取零
- range_extremes(seq)：全序列最小值与最大值，并逐段枚举段内极值做印证
- best_product(seq)：最大子段积，返回 ProductReport，含最优积、是否含零与左右下标
- 并列口径：先取长度最小，再取左端点最小
- last_scan：本次调用扫描过的元素总次数
- StatsErro：异常基类，下分 SeqErro 与 ParamErro

## 问题

求和靠枚举每一段再从段首累加，段数一多就是立方量级；长度上界与和最接近上界也是
逐段重新累加；极值对照对每一段重新扫描；最大子段积也逐段重新累乘。五条路都慢，也
拿不出任何计数说明更聪明的做法省了多少。调用方拿到最优值却不知道具体区间，更无法
与一条独立做法相互印证，边界情形只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_stats.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
