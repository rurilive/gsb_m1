# skipx

有序多重集合的朴素工具，纯标准库，无外部依赖。

## 现状

skipx/sortedbag.py 提供 SortedBag，排序数组存放全部元素，允许重复：

- SortedBag(values=())：从可迭代对象建集合，内部按升序排好
- insert(value)：插入一个元素，重复照插
- discard(value) / remove(value)：删一个等于 value 的元素，前者缺失返回 False，后者抛错
- find(value) / __contains__ / __len__ / is_empty / items()
- at(index) / pop_at(index)：升序第 index 个元素（从 0 起）
- rank(value)：严格小于 value 的元素个数
- predecessor(value) / successor(value)：严格小于 / 大于 value 的紧邻元素
- range_scan(lo, hi)：左闭右开区间 [lo, hi) 内按升序的全部元素
- probe_count(value)：查找时逐次比较的元素个数

内部查找走二分，但插入与删除都要把数组后半段整体搬移，是 O(n)；排名、前驱
后继靠定位或扫描，没有多层索引，也没有一层层下降的查找过程。规模一大，增删
就是瓶颈，查找的比较次数也压不下来。

## 问题

排序数组的插入删除都要搬移后半段，元素多时开销随规模线性增长；查找虽然二分，
却没有可以先定层再下降的多层索引结构，无从统计查找跨越了多少层、经过了几个
结点；层级随机、期望层高、当前层数这些可复现的统计一概没有。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_sortedbag.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+
- 任意增删序列后有序遍历与 SortedBag 对拍一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
