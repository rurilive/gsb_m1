# inclx

整数集合的朴素计数工具包，纯标准库，无外部依赖。

## 现状

inclx/counting.py 提供一份朴素计数工具 Counting，全部靠逐个枚举判定：

- count_not_divisible(limit, primes)：求不超过上界且不能被一组素数中任意一个整除的数的个数，从一到上界逐个取数、每个数再逐个素数试除
- count_coprime_in_range(low, high, numbers)：求闭区间内与一组数全部互素的数的个数，逐个求最大公约数
- count_union(sets)：把若干集合合并去重后数并集大小
- count_multi_condition(limit, conditions)：逐个取数并逐条判定条件
- CountingError：参数与取值范围错误的基类，继承 ValueError

## 问题

判断次数与上界成线性，每次判断还要对素数集合再走一遍，总代价近似上界乘以素数个数，
上界一大就慢得不可接受；区间互素计数同样逐个求最大公约数；并集只能靠逐元素合并，
没有容斥口径。模块没有提供任何与逐数判定等值的快速路径。

## 目标

见任务描述。约束：

- tests/test_counting.py 是基线，一字不许改且必须全绿
- 新行为另开测试文件
- 纯标准库，无第三方依赖，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
