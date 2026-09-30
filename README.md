# dsu

不相交集合与动态连通性的朴素实现雏形，纯标准库，无外部依赖。

## 现状

`dsu/core.py` 提供 `NaiveDisjointSets`，只有一条最直白的路：

- `add(x)`、`contains(x)`、`elements()`：登记元素、是否登记、全部已登记元素
- `find(x)`：所在集合的一个代表元，逐个集合、逐个成员地线性扫描
- `connected(a, b)`：两点是否连通，同一点恒连通
- `size(x)`、`group_members(x)`、`groups()`、`component_count()`、
  `component_sizes()`：集合大小、成员与整体统计
- `union(a, b)`：把 b 集合的成员逐个改名挂到 a 集合的代表元下，真正合并才返回真
- `union_weighted(a, b, w)`：建立关系，令 a 相对 b 的偏移恰为 w
- `relate(a, b)`：a 相对 b 的偏移，不同集合抛 `NotConnected`
- `add_edge(u, v)`、`would_close_cycle(u, v)`：动态连通性下加边与环检测
- `count_merges()`、`count_queries()`、`count_renames()`、`count_scans()`、
  `cost_report()`：合并、查询、改名与扫描的规模计数

现状全部走朴素口径：合并把一侧成员逐个改名挂到另一侧的代表元下，查询逐元素线性
扫，带权偏移逐元素重算，环检测也靠一次线性扫描的归属查询。口径直白、结果确定，
但每次合并与查询的代价随集合规模线性增长，合并与查询一多就退化到平方量级。异常
基类是 `Erro`，元素编号不合法抛 `BadElement`，查询未登记元素抛 `UnknownNode`，
越界求偏移抛 `NotConnected`，偏移不是整数抛 `BadWeight`。

## 问题

没有路径压缩与按秩或按大小合并，连通查询与集合合并拿不到近常数级的均摊代价；带权
偏移只靠逐元素重算，缺少压缩路径时同步累加维护偏移的口径；动态连通性下的环检测也
没有与压缩结构对齐的独立路，更读不到朴素改名规模与压缩口径的对照。

## 目标

见任务描述。约束：

- `tests/test_baseline.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件，基线路径不许删除
- 纯标准库，不引第三方

## 运行

```bash
python3 demo.py                          # 朴素改名与线性扫描演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
