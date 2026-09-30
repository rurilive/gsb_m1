# domtree

内存里的朴素支配关系工具，纯标准库，无外部依赖。

## 现状

`domtree/dominator.py` 提供 `DirectedGraph`，内部是一张有向图的邻接表，
支配关系全靠逐点删点判可达现算：

- `add_node(n)` / `add_edge(u, v)`：登记节点与有向边，两端懒登记
- `nodes()` / `edges()` / `neighbors(u)` / `has_edge(u, v)`：结构与查询
- `reachable_from(src)`：从 src 出发可达的节点集合，含 src 自身
- `reachable_without(src, removed)`：把 removed 拿掉之后的可达集合
- `dominators(start)`：每个可达点的全部支配点，按升序
- `immediate_dominators(start)`：每个可达点的直接支配点，起点为 None
- `dominator_edges(start)`：支配树的边，按字典序
- `dominates(start, u, v)`：单次删点判可达
- `children_of(start, u)`：支配树上 u 的直接孩子
- 异常统一挂在 `Erro` 下：`IllegalArgument`、`UnknownNode`

## 问题

求一个起点的全部支配点时，对起点可达的每个候选点都单独把它拿掉、再单独
从起点搜一遍，代价按点数乘边数甚至更高增长；点一多就顶不住。结论算完即
弃、从不留存复用，同一个起点上问得越多越亏，每问一次都把同样的删点搜索
重走一遍。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_dominator.py` 基线保持一致（基线一个字不改）
- 新行为另开测试文件，纯标准库
- 逐点删点这条现算路径保留，两条路对同一批数据给出的事实必须一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
