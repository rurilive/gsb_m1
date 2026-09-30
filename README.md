# sparsetable

静态区间最值工具，纯标准库，无外部依赖。

## 现状

sparsetable/rmq.py 提供 NaiveRMQ：

- __init__(data)：整数序列，非列表元组或含非整数元素即报 IllegalArgument
- query_min(l, r)：半开区间 [l, r) 的最小值，空区间返回 None
- query_max(l, r)：半开区间 [l, r) 的最大值，空区间返回 None
- query_argmin(l, r)：最小值首次出现的下标，空区间返回 None
- query_many(ranges)：对一批区间逐个求最小值，每项各自重扫
- value_at(i) / as_list() / __len__：读取序列
- 异常统一挂在 Erro 下：IllegalArgument

内部只留一个整数列表。每问一次区间，就把区间从头整个扫一遍，既没有
预处理，也没有下标缓存、二维结构或能共享预处理的批量路径；区间一多，
同一段就被反复白扫。

## 问题

逐项扫描使单次查询是线性代价，查询条数一大就白扫；没有稀疏表、没有
区间最大值下标、没有二维子矩阵查询、也没有能共享预处理的批量处理。

## 目标

见任务描述。约束：

- tests/test_rmq.py 是行为基线，一个字不许改，必须原样全绿
- 新行为另开 tests/test_sparse.py，用固定序列与逐字断言
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
