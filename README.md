# graphx

图论工具包，纯标准库，无外部依赖。

## 现状

`graphx/net.py` 提供 `FlatNet`，是一张朴素有向图：

- `add_node(name)`：登记节点，重复登记不改动已有结构
- `add_edge(u, v, cap)`：加一条带容量的有向边，容量只被原样记录
- `neighbors(u)`：按出边添加顺序返回邻点与容量
- `reachable(s, t)`：一次深度优先遍历判断可达性
- `bfs_order(s)`：从起点出发的广度优先顺序
- `edges()` / `node_count()` / `edge_count()` / `out_degree(u)`：结构统计

整包只做遍历，完全没有流量概念。容量只是一个被随手记下的数字，不参与
任何计算：可达判断不设容量门槛，一条容量为零的边照样算连通，也答不出
最大流、最小割、匹配、边不交路径这类与容量有关的问题。未知节点抛
`UnknownNode`，其余业务错误继承 `GraphError`。

## 问题

只有遍历，没有流量。容量记了却不用，任何需要比较流量大小的问题都无从
下手，也无法把二分图匹配、边不交路径这类问题归约到统一口径上求解。

## 目标

见任务描述。约束：

- `tests/test_net.py` 行为基线保持不变（基线一个字不改且必须全绿）
- 新行为另开 `tests/test_flow.py`
- 纯标准库
- 新增异常继承 `GraphError` 基类

## 运行

```bash
python3 demo.py                          # 朴素遍历演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
