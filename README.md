# winx

定长滑动窗口的统计工具集，纯标准库，无外部依赖。

## 现状

`winx/window.py` 提供一份朴素但正确的实现 `WindowStats`：给定序列与窗口大小，
对每个窗口从头把窗口内元素重新扫一遍。

- `WindowStats(window_size)`：构造时校验窗口大小必须是正整数
- `maxima(seq)` / `minima(seq)`：逐窗口线性扫描取极值
- `medians(seq)`：逐窗口排序取中位，偶数窗口取中间两个的算术平均
- `sums(seq)`：逐窗口累加求和，返回浮点
- `distinct_counts(seq)`：逐窗口去重计数
- `kth_smallest(seq, k)`：逐窗口排序后取第k小，k从0起算
- `rank(seq, value)`：逐窗口数小于该值的元素个数

模块根另有一组便捷函数 `window_max`、`window_min`、`window_median`、`window_sum`、
`window_distinct`、`window_kth`、`window_rank`，与实例方法口径一致。
异常统一挂在 `winx.window.WinxError` 之下（也可从包根 `winx` 导入）：
`InvalidWindowSizeError`、`InvalidSequenceError`。

## 问题

每个窗口都要从头重扫一遍，窗口一滑就整段重算：取极值是线性的、取中位要重排序、
求和与去重要重新累加与重新插入集合。序列长、窗口大时重复劳动成倍放大，
始终停留在朴素口径上，没有单调队列、有序结构、前缀和与增量计数这些流式做法。

## 目标

见任务描述。约束：

- `tests/test_window.py` 是基线，一字不许改且必须全绿
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
