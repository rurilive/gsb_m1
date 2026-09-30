# pushrelabel

有向容量网络的最大流与最小割，纯标准库，无外部依赖。容量网络这种对象在
调度、匹配、割容量评估里很常见，pushrelabel 就是承载这层计算的那一层。

## 现状

`pushrelabel/flow.py` 提供一份朴素实现：

- `FlowNetwork`：有向容量网络，允许平行边、禁止自环
  - `add_node` / `nodes` / `has_node` / `node_count`：节点登记与查询
  - `add_edge(src, dst, capacity)`：加边，容量在加边处校验
  - `edges` / `edge_count` / `neighbors(u)`：边与邻居查询
  - `augment(source, sink)`：广度搜索找一条增广路并沿路推流，返回本次推了多少
  - `reachable_from(source)`：残量网络上从源点可达的节点
  - `copy` / `value(source, sink)`：复制网络与流量值
- `max_flow(network, source, sink)`：反复增广求最大流，返回 `FlowResult`
- `min_cut(network, source, sink)`：按残量可达性读出最小割 `MinCutResult`
- 异常体系在同一模块内：`Erro` 基类，以及 `InvalidCapacityError` /
  `NodeNotFoundError` / `SelfLoopError` / `SourceSinkError` / `NoPathError`。

残量网络用邻接表记录，广度搜索一次只找一条增广路，沿路按用量最小的残量逐条
推流；最小割按汇点在残量网络里不可达来划分源点侧与汇点侧。容量允许为 0，
不接受负数、布尔值与非整数；自环一律拒绝。

## 问题

现有实现结果是对的，但推进方式太粗：一次只找一条增广路，增广路数量与容量
同阶，容量一大就要反复增广很多次；没有预流，也没有高度标记，无法说明先沿
源点出边饱和推流、再用推流重标记把余流顶回去的做法到底省了多少；活跃点的
推进次数与重标记次数这两个量根本没被统计；边界也只覆盖到平行边和一两条零
容量边。

## 目标

见任务描述。约束：

- `tests/test_flow.py` 行为基线保持不变（基线一个字不改）
- 新行为另开 `tests/test_flow_advanced.py`
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py                          # 朴素最大流与最小割演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
