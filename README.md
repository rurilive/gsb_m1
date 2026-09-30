# bridgecut

纯标准库的无向图割边、割点与双连通分量雏形，无外部依赖。

## 现状

bridgecut 里的 graph 模块提供一张无向图，结点取 0 到 n-1，边按输入先后编号：

- UndirectedGraph(n, edges)：构造时校验结点数、边形状与端点范围，允许重边与自环
- node_count、edge_count、nodes、edges：取规模与全部结点、边
- is_connected、connected：整图是否连通、两点是否在同一分量
- bridges、articulation_points：割边与割点，按输入序或编号升序给出
- edge_components、vertex_components：边双连通分量与点分量
- bridge_tree：把点分量缩点、割边变边之后得到的桥树
- must_pass_edge、must_pass_node：两点之间是否必经某条边或某个点
- counters、reset_counters：记录重判连通性次数与重扫边次数

## 问题

每条边、每个点都尝试删掉一次，再用搜索重判全图是否变松散，
双连通分量又靠枚举连通性变化来分；重判次数随边数与点数线性增长，
每次重判还要把整张图的边重扫一遍，规模一大就明显慢下来。

## 目标

在当前基础上补出以深度优先搜索时间戳与追溯值一次求出全部割边割点，
并据该结构分出边双与点分量、求缩点桥树与两点必经判定，另用一条
独立做法逐项对照，见任务描述。约束：

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
