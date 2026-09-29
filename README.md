# lcalib

最近公共祖先工具，纯标准库，无外部依赖。

## 现状

`lcalib/lca.py` 提供 `NaiveLca`：

- `parent(u)`：父节点，根返回 None
- `depth(u)`：沿父指针数到根的深度（根为 0）
- `lca(u, v)`：最近公共祖先
- `dist(u, v)`：两点间路径的边数
- `is_ancestor(u, v)`：祖先关系（节点是其自身的祖先）
- `query_many(queries)`：对一批 (u, v) 逐个求最近公共祖先
- `root` / `nodes()` / `children(u)` / `__len__` / `__contains__`：读取树

用一组 (父, 子) 边建有根树。每次查询都沿父指针逐层上爬：
求深度要一路数到根，求最近公共祖先要先把较深者爬到同层再一起上爬，
求距离与祖先关系同样靠逐层上爬。深链上单次查询退化成线性，
批量查询里同一节点被反复重爬。非法节点抛 `LcaNodeError`，
它继承自基类 `LcaError`。

## 问题

逐层上爬使得单次查询代价随深度线性增长，深链上退化成线性，
查询一多就白爬；没有预处理、没有倍增表、没有欧拉序、没有稀疏表、
也没有能共享预处理的批量路径。

## 目标

见任务描述。约束：

- `tests/test_lca.py` 是行为基线，一个字不许改，必须原样全绿
- 新行为另开 `tests/test_ancestor.py`，用固定树与逐字断言
- 纯标准库
- 新异常统一继承 `LcaError`

## 运行

```bash
python3 demo.py                           # 最近公共祖先现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

（实现后补，10 行以内）
