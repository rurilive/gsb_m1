# reroot

树上换根聚合量的求解器，纯标准库，无外部依赖。

## 现状

`reroot/core.py` 提供 `Reroot`：

- `load(n, edges)`：载入结点数为 `n` 的无向树，`edges` 是 `(u, v)` 无序点对列表
- `node_count()`：结点个数
- `subtree_sizes(root)`：以 `root` 为根时，结点编号到其子树大小的映射
- `distance_sum(root)`：`root` 到树上其它所有点的距离之和
- `all_distance_sums()`：逐结点单独当根的全量距离之和
- `deepest_subtree(root)`：以 `root` 为根时从它出发的最远步数
- `all_deepest_subtrees()`：逐结点单独当根的全量最远步数
- `visit_count()`：逐根单独深搜口径下访问结点的总次数

现状是朴素做法：对每个结点 `r`，都把 `r` 单独当作根，从 `r` 出发重新做
一次完整深搜，现场求出以 `r` 为根时的父子关系与各聚合量。求全量答案时，
每个结点都要重走整棵树，代价退到平方量级。异常基类是 `RerootError`，
输入不合法抛 `RerootInputError`，查询未登记结点抛 `UnknownNodeError`，
边连不成一棵树抛 `DisconnectedError`。

## 问题

没有第一遍自根向下、第二遍自上而下复用父结点结果的做法，每个根都从头
重走整棵树，规模一大就慢；也没有另一条独立口径可以在固定输入上与新
做法逐项对照。

## 目标

见任务描述。约束：

- `tests/test_reroot.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素统计演示
python3 -m unittest discover -s tests    # 行为基线测试
```

（实现后补，10 行以内）
