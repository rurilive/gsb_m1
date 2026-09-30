# divblock

一个纯标准库的数论求和工具箱，无外部依赖。做约数统计、互素计数、函数前缀和
这类整除相关的累加时，总会碰到上界一大跑不动的情形，divblock 就是这一层。

## 现状

- `divblock/sumtools.py`：数论求和写成几类累加，某数论函数的区间前缀和、各数
  约数个数之和、不超过上界与某数互素的个数之和、按整除商的跳跃求和，一律用
  最直白的逐个枚举，结果精确，规模一大就慢。
- `totient_sieve`、`mobius_sieve`：朴素筛出欧拉函数表与莫比乌斯函数表。
- `totient_prefix_upto`、`mobius_prefix_upto`、`range_totient_sum`、
  `range_mobius_sum`：函数值的前缀和与区间和，逐个累加。
- `divisor_count_upto`：各数约数个数之和，逐个除。
- `coprime_count_upto`：不超过上界与某数互素的计数之和，逐个比对最大公约数。
- `best_divisor_number_upto`、`best_divisor_number_count`：约数个数最多且取值
  最小的那个数及对应约数个数，逐个重数因数。
- `naive_scan_count`、`naive_pair_count`：露出逐个枚举的项数与配对量级。
- `divblock/GcdSumError`：所有可诊断错误的基类，带 `message`、`position`
  与 `data`。

## 问题

现在只有一条路子，逐个枚举每个数甚至每对数，上界一大就落到线性到平方量级，
慢得跑不动；整除商相同的那段连续区间没有被归并成块，看不出块数与枚举项数的
规模差；几类累加各写各的小函数，互相印不上，也没有第二条路径用来互相印证。

## 目标

见任务描述。约束：

- `tests/test_sumtools.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
