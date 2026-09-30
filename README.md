# lctx

内存里的朴素动态森林，纯标准库，无外部依赖。

## 现状

`lctx/dtree.py` 提供 `Dtree`，用无向邻接集合维护一片带点权的动态森林：

- `add_node(u)`：登记一个孤立节点，点权默认 0
- `link(u, v)` / `cut(u, v)`：连边与断边，连边会拒绝自环、重复边与成环
- `neighbors(u)` / `has_edge(u, v)` / `edge_count()`：邻接视图
- `connected(u, v)`：从一端做一次深度优先判断连通
- `component_count()`：每次从头把整片森林数一遍连通分量
- `path_sum(u, v)` / `path_max(u, v)`：沿路径逐节点求和或取最值
- `path_add(u, v, delta)`：沿路径逐节点改写点权
- `make_root(u)` / `component_root(u)`：换根与读回根标记
- `subtree_sum(u, root)`：给定根时把子树逐节点走一遍再加
- `set_weight(u, x)` / `weight(u)`：点权读写
- `reset_cost()` / `last_cost()`：上一次操作看过的节点数

## 问题

每次连通判断、路径统计、子树求和与分量计数都要当场遍历：`connected` 做一次
深度优先，`path_sum` 先把路径找出来再逐节点累加，`subtree_sum` 把子树逐节点
走一遍，`component_count` 更是每次都从头数，`make_root` 则把整棵树的根标记
重扫一遍。动态改动一多、链一长就白走，反复查询与更新都顶不住。

## 目标

在当前基础上，以动态树（优先路径与实链剖分）为核心把 `Dtree` 扩成能动态
连边断边、对数级回答路径与子树统计的森林工具，见任务描述。约束：

- 现有行为与 `tests/test_dtree.py` 基线保持一致（基线一个字不改）
- 新行为另开 `tests/test_dynamic_tree.py`，纯标准库
- 邻接集合那套遍历路径保留，两条路对同一批数据给出的事实必须一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
