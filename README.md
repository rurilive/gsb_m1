# graphx

邻接表存图的连通性小工具，纯标准库，无外部依赖。

## 现状

graphx/graph.py 提供 Graph：

- add_node(value) / add_edge(u, v)：建图，节点只要求可哈希
- nodes() / edges() / has_node(value)：取全图结构
- node_count() / edge_count() / neighbors(value) / out_degree(value)
- connected_components() / component_count() / is_connected()
- reachable(a, b)：两点是否同属一个连通块，方向不参与判断
- split_vertices()：割点，逐个删点后重扫全图比对分量个数
- bridges()：割边，逐条删边后重扫全图比对分量个数
- bidirectional_edges()：双路径互达边，即全部非割边
- scc()：强连通分量，以某点为核心反复删点，用两两互达把同分量筛出来
- sweep_count() / reset_sweep_count()：全图重扫次数的观测口径

异常统一继承 GraphxError：UnknownNodeError 在引用不存在的节点时抛出，
EmptyGraphError 在空图上取强连通分量时抛出。

每条判断都从起点重新做一次深度优先搜索，全图重扫次数随点与边的规模一起涨，
结果对、规模一大就慢；分量只有成对询问拼出来的近似答案，没有分量编号实体。

## 问题

割点要对每个点各重扫一遍、割边要对每条边各重扫一遍，合起来是逐点逐边乘全图
重扫；强连通分量更重，每筛一个点都要正反各扫一遍，还不能给出分量编号与分量图。
调用方拿不到缩点后的有向无环图，也拿不到拓扑序，只能靠两两判断自己拼，既慢又散。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_graph.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
