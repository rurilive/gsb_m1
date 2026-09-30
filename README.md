# prefixkit

字符串前缀函数与周期相关问题的朴素工具，纯标准库，无外部依赖。

## 现状

prefixkit/prefix.py 提供 PrefixKit：

- PrefixKit(pattern="")：收下模式串，非字符串立刻报错
- pattern()：取回模式本身
- prefix_function()：前缀函数，返回长度 len(pattern)+1 的列表
- prefix_value(k)：第 k 个前缀（长度为 k）的前缀函数值
- find_occurrences(text)：模式在文本中全部出现位置的起始下标，升序
- count_occurrences(text)：出现位置个数
- count_prefix_occurrences()：每个前缀在原串中的出现次数（含重叠）
- period_info()：最短循环节与周期判定信息
- min_period()：最短循环节长度
- prefix_steps()：最近一次求前缀函数的比较次数
- search_steps()：最近一次查找的比较次数

求每个前缀的前缀函数值，就把该前缀的每个真前缀枚举出来、逐字符比对看是否同时
是后缀，取最长者；在文本里找模式，对每个对齐位置暴力比对；判断最短循环节与周期，
枚举所有能整除长度的块长逐个验证；统计各前缀出现次数，也先枚举候选再验证。
规模一大就是平方甚至立方级，结果正确，速度不快，也没有任何一次线性扫描复用
已完成前缀函数的机制。

## 问题

每求一个前缀的函数值都要把该前缀的全部真前缀枚举一遍，长度一大就是平方级；
查找、周期判定、前缀出现统计都建立在逐个候选验证之上，字符高度重复时退化明显；
两条路径之间没有一套可以一次线性扫描、复用已完成值并支撑查找与周期的前缀函数
机制可比。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_prefix.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
