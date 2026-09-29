# ratestore

内存时序指标直方图，纯标准库，无外部依赖。

## 现状

`ratestore/store.py` 提供一份朴素累加器 `RateStore`：

- `RateStore()`：无参构造，按 label 维度各存一份计数与总和
- `record(value, label=DEFAULT_LABEL)`：累加一次样本，返回 `self`
- `count(label)` / `sum(label)` / `mean(label)`：取该维度的个数、总和与平均值
- `labels()`：出现过的维度，升序去重列表
- `merge(other)`：把另一份累加器按维度并入自身，返回 `self`
- `RateStoreError`：参数错误的基类，继承 `ValueError`

`DEFAULT_LABEL` 取 `"default"`，各维度之间完全隔离，查询都是只读的。

## 问题

累加器只保留个数与总和，不保留任何时间信息，`count`、`sum`、`mean`
拿到的都是从进程启动至今的全量口径，既没法只看最近一段时间，
也算不出分位数。维度只能靠 label 一个个查，没有聚合口径；
没有时钟注入，时间相关的行为无法在测试里确定性复现；
多线程并发累加时也没有任何同步保护。

## 目标

见任务描述。约束：

- `tests/test_store.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_histogram.py`
- 纯标准库，无第三方依赖，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）