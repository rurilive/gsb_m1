# treecover

树上覆盖工具的朴素基线，纯标准库，无外部依赖。

## 现状

treecover/tree.py 里是 Tree，一棵无向简单树，顶点用整数编号，边用邻接表逐条
累积，边的权重可正可负可零：

- add_edge(u, v, weight=1)：加一条无向边，两端各记一次
- add_vertex(node)：登记孤立顶点，用来构造单节点这类退化输入
- vertices / neighbors / edges / edge_weight：列顶点、列邻接点、列无向边、取边权
- vertex_weights(weight_map)：按映射给出每点权，缺省全为 1

同一模块 tree.py 里还有几个朴素求解，都靠枚举顶点子集、逐个检查再取最值：

- enumerate_subsets / subset_check_count：按字典序枚举全部子集，并报出二的节点数次方
- is_dominating_set / is_vertex_cover / is_independent_set：逐个检查一个集合是否满足要求
- min_dominating_set / min_vertex_cover / max_independent_set：枚举全部子集取最小或最大
- weighted_min_dominating_set / max_weight_independent_set：带点权的枚举求最值

## 问题

只有这一层朴素枚举，规模一大就崩。求最小支配集、最小点覆盖、最大独立集，都要数遍
二的节点数次方个子集再逐个检查，六个点的树还算得动，十几个点就慢得难堪；三条结论
各算各的，互相之间没有第二把尺子来印证，最小值与最大值到底对不对也无从核对。带点
权的最小支配集与最大权独立集同样只有枚举一条路，点权为零或负数时更是连口径都没写
死。单节点、两节点、链、星形、完全二叉树、所有方案并列、空树、非法输入这些边界，
眼下既没有明确口径，也没有统一错误类型；暴露规模对照的入口也只有子集枚举次数这一
个数字。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_covering.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
