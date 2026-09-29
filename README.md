# lctlib

内存里的朴素动态森林，纯标准库，无外部依赖。

## 现状

`lctlib/forest.py` 提供 `FlatForest`，用无向邻接集合维护一片带点权的
动态森林：

- `add_node(u)`：登记一个孤立节点，点权默认 0
- `link(u, v)` / `cut(u, v)`：连边与断边，连边会拒绝自环、重复边与成环
- `neighbors(u)` / `has_edge(u, v)` / `edge_count()`：邻接视图
- `connected(u, v)`：从一端做一次深度优先判断连通
- `path_sum(u, v)` / `path_add(u, v, delta)`：沿路径逐节点累加或改写点权
- `subtree_sum(u, root)`：给定根时把子树逐节点走一遍再加
- `component_count()`：每次从头把整片森林数一遍连通分量
- `set_weight(u, x)` / `weight(u)`：点权读写

## 问题

每次连通判断、路径统计与分量计数都要当场遍历：`connected` 做一次深度
优先，`path_sum` 先把路径找出来再逐节点累加，`subtree_sum` 把子树逐节点
走一遍，`component_count` 更是每次都从头数。动态改动一多、长链一长就
白走，反复查询与更新都顶不住。

## 目标

在当前基础上，以动态树（链剖分或等价结构）为核心把 `FlatForest` 扩成
能动态连边断边、对数级回答路径与子树统计的森林工具，补出动态连边断边
后的连通性、路径点权和与点权加、点权与子树查询、连通分量计数、边存在
性口径、复杂度计数、边界与确定性，见任务描述。约束：

- 现有行为与 `tests/test_forest.py` 基线保持一致（基线一个字不改）
- 新行为另开 `tests/test_link_cut.py`，纯标准库
- 邻接集合那套遍历路径保留，两条路对同一批数据给出的事实必须一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
