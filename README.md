# diffx

数组区间修改与查询工具包，纯标准库，无外部依赖。

## 现状

`diffx/array.py` 提供 `DiffArray`、`DiffMatrix` 与几个辅助入口，能力朴素但正确：

- `DiffArray(values)` / `DiffArray.zeros(size)`：维护一组数，保留下标顺序，构造时校验规模与元素
- `value_at(index)`：按下标取当前位置的值，越界即报错
- `range_add(left, right, delta)`：闭区间批量加，逐元素遍历改写整段
- `prefix_sum(index)` / `range_sum(left, right)` / `total_sum()`：每次都现场重扫整段累加
- `replay(operations)`：按离线操作序列逐条做区间加，最后返回整数组
- `change_count()` / `reset_change_count()`：改动点计数按一次改写一个元素累加，查询也计入
- `DiffMatrix(rows)` / `DiffMatrix.zeros(rows, cols)`：二维数组，`region_add` 用二重循环逐格改写
- `flatten`、`elementwise_add`、`elementwise_equal`：整组展开与逐项运算，形状不一致即报错

异常统一挂在 `diffx.array.DiffError` 之下（也可从包根 `diffx` 导入）：
`InvalidSizeError`、`InvalidIndexError`、`InvalidRangeError`、
`InvalidMatrixError`、`InvalidShapesError`。

## 问题

每次区间修改都要按区间长度逐元素改写，一次改动就是整段的工作量；每次查询还要
重新扫一遍整段求和。没有任何把批量修改降成少数几次改动的结构，改动点计数也
只有逐元素改写这一个口径，调用方既看不到省下了多少工作，也没法对照优化效果。

## 目标

见任务描述。约束：

- `tests/test_array.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
