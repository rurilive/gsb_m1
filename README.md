# blossom

一个只用 Python 标准库的一般图匹配小工具，纯内存，无外部依赖。

## 现状

`blossom/matching.py` 提供 `GraphMatcher`，维护一张一般图：点是任意可
哈希对象，边无向，用对集合表示，重复边只算一次，自环与空点当场拒掉。
当前所有结果都由回溯枚举驱动：

- `add_edge(u, v)`：加一条无向边，重复边不重复计，返回自身
- `nodes` / `edges()` / `node_count()` / `edge_count()` / `neighbors(u)`：
  读图，边按两端稳定排序后给出
- `has_edge(u, v)`：两点之间是否有边
- `max_matching_size()`：回溯枚举全部边组合，取条数最多的匹配
- `max_matching()` / `matched_to(u)`：给出一个最大匹配方案并回查配对
- `is_maximum(matching)`：把给定匹配的大小与真正最大值比
- `perfect_matching_exists()`：最大匹配是否覆盖全部点

## 问题

枚举的量随边数指数增长：求最大匹配要把每条边配或不配的组合挨个走一遍，
判断一个匹配是否最大又要把这些组合再走一遍。点数、边数一多就迅速撑不
住，而且当前既没有增广的观念，也没有任何计数能说明一条更聪明的做法省了
多少。

## 目标

在当前基础上，以带花树为核心把 `GraphMatcher` 扩成一般图匹配工具集，
见任务描述。约束：

- 现有行为与 `tests/test_baseline.py` 基线保持一致（基线一个字不改）
- 纯标准库，不得引入任何外部依赖
- 枚举那套朴素路径保留，新老两条路对同一批数据给出的事实必须一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
