# sortlab

面向整数序列的排序工具箱，纯标准库，无外部依赖。

## 现状

`sortlab/sorter.py` 提供 `NaiveSorter`，对整个列表直接排序：

- `sort(values)`：返回升序副本，不修改入参
- `sorted(values)`：`sort` 的别名

它用选择排序按整数大小比较，没有分桶、没有稳定性保证、没有键函数。
`tests/test_sorter.py` 锁住这些行为。

## 目标（见任务描述）

把 `sortlab` 从朴素排序扩成基数排序工具，新增稳定基数排序、有符号与大整数支持、
跨基数一致、自定义键函数、超内存块的分块归并与外部归并，并与朴素排序对拍。
全部仍在 `sortlab` 包内，纯标准库。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
