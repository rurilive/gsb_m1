# spannex

生成树工具包，纯标准库，无外部依赖。

## 现状

`spannex/graph.py` 提供 `BruteSpan`，只回答一张无向图是否连通：

- `add_node(name)`：登记节点，重复登记不改动已有结构
- `add_edge(a, b)`：加一条无向边，端点必须已登记
- `nodes()` / `edges()`：按登记与加入顺序返回节点与边
- `has_edge(a, b)`：两点之间是否有边，无向
- `reached_from(start)`：从起点出发反复扫描全量节点求可达集合，按登记顺序
- `connected(a, b)`：两点是否连通
- `is_connected()`：整张图是否连通，空图与单点图视为连通

内部不维护邻接表，每次判断都重新对全量节点反复扫描，没有排序，没有并查集，
也不产出任何生成树。未知节点抛 `UnknownNode`，其余业务错误继承 `SpannError`。

## 目标

见任务描述。约束：

- `tests/test_graph.py` 行为基线保持不变（基线一个字不改且必须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素连通演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
