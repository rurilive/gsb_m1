# dagtopo

纯标准库的有向图拓扑序、依赖调度与可达性计数雏形，无外部依赖。

## 现状

dagtopo 里的 graph 模块提供一张有向图，点取 0 到 n-1，边按输入先后编号：

- DirectedGraph(n, edges)：构造时校验点数、边形状与端点范围，允许自环与平行边
- node_count、edge_count、nodes、edges：取规模与全部点、边
- in_degrees：每个点的当前入度
- has_cycle、topological_order：是否有环、一个拓扑序，可选点较多时取编号最小的那个，有环时拓扑序返回 None
- cycle_nodes：一个有环图里具体环上的点，按走环的先后给出
- earliest_start、critical_path：每个点的最早开始时间与关键路径，有环时返回 None
- reachable_counts、reverse_reachable_counts：每个点能到达的点数与能被多少点到达
- counters、reset_counters：记录扫点次数与重扫边次数

## 问题

拓扑序靠反复在整张图里从头线性扫描找当前入度为零的点，找到一个取走一个，
再沿着它出去的每一条边把另一端点的剩余入度重算一次；每取一个点都要从头再扫一轮，
每轮还要把整张图的边重扫一遍。最早开始时间与关键路径也跟着每一轮重扫一遍，
可达计数则是每个点各做一次搜索。轮数与每轮重扫的点数、边数双双上去，规模一大就明显慢。

## 目标

在当前基础上补出用入度队列一次求出拓扑序、在拓扑序上求最早开始时间与关键路径、
对有环图给出一个具体环、每点的可达与反向可达计数，另用一条独立做法逐项对照，见任务描述。约束：

- 现有行为与 tests/test_graph.py 基线保持一致（基线一个字不改）
- 纯标准库
- 新老两条路径对同一批图的全部结果必须逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
