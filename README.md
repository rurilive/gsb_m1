# lcatree

纯标准库的有根树与路径查询雏形，无外部依赖。

## 现状

lcatree 里的 tree 模块提供一棵用父指针表示的有根树：

- Tree(parents)：字典建树，根记 None，构造时校验唯一根、无环、父结点存在
- root、nodes：取根与全部结点编号
- path_to_root、depth：沿父指针逐级上溯得到到根的路径与深度
- is_ancestor：逐级上溯判断祖先关系
- lca：两条到根路径逐项比对得到最近公共祖先
- distance、path、path_sorted：求距离、路径、按编号排序的路径
- on_path、paths_intersect：路径点判定与路径相交判定

## 问题

每次查询都各自沿父指针一步步走到根，把整条路径记下来再逐项比对，
查询一多、树一深，逐级上溯的次数就随深度线性增长，整体拖不动。

## 目标

在当前基础上补出倍增祖先表，并据它支撑距离、路径判定、路径排序与
路径相交，另用一条独立做法逐项对照，见任务描述。约束：

- 现有行为与 tests/test_tree.py 基线保持一致（基线一个字不改）
- 纯标准库
- 新老两条路径对同一批树的全部查询必须逐项一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
