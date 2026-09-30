# knapsackx

大容量零一背包的朴素工具，纯标准库，无外部依赖。

## 现状

knapsackx/knapsack.py 提供 Knapsack：

- Knapsack(items=())：把若干对重量与价值收成一批物品，非整数、负数立刻报错
- add(pair)：追加一个物品，返回自身以便链式调用
- items()：取回物品列表，对外只读
- reachable_set(capacity)：容量上界内全部可达重量，升序列表
- best_value(capacity)：容量上界内能取到的最大总价值
- exact_fit(capacity)：恰好装满容量的一组装入方案，无解时报错
- at_least(capacity)：总重量不小于容量的一组装入方案
- plan_value(capacity)：取最大价值的一组装入方案
- update_count()：上一次计算里逐格更新容量表的次数

内部用一长条布尔格子记录可达重量，用二维整型表逐格推进最优价值，
容量或价值一大就是二重循环加整条表格，但结果正确。

## 问题

表达可达容量集合的只有一条条布尔格子，每加一个物品都要沿容量轴逐格更新，
容量一大格子就长，复数批容量反复跑更是把同一段格子一再重算；最优价值又另
开二维整型表逐格填，容量与价值双高时内存与耗时同时吃紧；恰好装满、上界内
最大值、按价值维独立推进的对拍口径目前都还没有。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_knapsack.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
