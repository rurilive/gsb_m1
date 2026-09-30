# rangeseg

一个只用 Python 标准库的小仓库，提供一条整数序列上的区间操作工具集。

## 现状

- 包名 `rangeseg`，核心类 `RangeSeq`，位于 `rangeseg/seq.py`。
- 内部只有一份平铺的 list，元素按构造给出的顺序保存，允许负数。
- `sum(left, right)` 逐个累加半开区间 `[left, right)` 内的元素，空区间返回 0。
- `add(left, right, delta)` 用循环对区间内的每个元素逐个改写。
- `assign(left, right, value)` 用循环把区间内的每个元素逐个改写成 value。
- `min_val` / `max_val` 逐个比较出区间最值，空区间抛 `EmptySequenceError`。
- `get(index)` / `set(index, value)` 按下标读改单点，越界抛 `IndexOutOfRangeError`。
- `replay(values, operations)` 在副本上依次回放一串操作，返回末态与逐步返回值。
- `taken()` 返回至今逐项扫描累计访问过的元素次数。
- 所有自定义异常继承自 `RangeSegError`。

## 问题

每次区间求和、区间加、区间赋值或者区间最值都要把整段从头扫一遍，单点
读改虽然是常数量级，但改完之后没有任何聚合量可以复用。规模一上来，每个
区间操作的代价就随区间长度线性上涨，序列里也没有任何树形结构或懒标记，
一次区间加只能老老实实落到区间里的每一个元素上。

## 目标

把核心从平铺列表扩成以带懒标记的线段树为核心的区间统计工具集：区间加与
区间求和、区间最值在对数代价内完成，懒标记只在必要时下推并暴露下推计数；
另起一条独立的分块或前缀和差分朴素口径做小规模交叉核对，新老两条路径对
同一批固定输入逐项一致；再补一条可持久化或带权能力并各配独立印证。原先
那套朴素列表操作保留下来做对照。

## 运行

```
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
