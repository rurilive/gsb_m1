# columnkit

纯标准库的内存查询雏形，无外部依赖。

## 现状

columnkit/table.py 提供一张行式表 Table：

- Table(name, rows, columns=None)：具名表，逐行拷一份，列缺省按行里键的顺序推导
- filter(predicate)：按谓词逐行判断，挑出满足条件的行，返回一张新表
- select(table, predicate)：对表做一次过滤的便捷入口
- count、columns、to_dicts、迭代都对外只读，改不动原表

## 问题

只有一层朴素过滤：谓词一律在取数的最后一步生效，用不上的列也被完整读进来，
两张表想关联只能自己在外层循环，分组统计更是无从谈起。算子是一堆散落的函数，
既没有统一的执行计划，也没有任何可解释性，慢在哪里看不出来。

## 目标

在当前基础上补出谓词下推、投影裁剪、哈希连接、分组聚合与执行计划解释，
见任务描述。约束：

- 现有行为与 tests/test_table.py 基线保持一致（基线一个字不改）
- 纯标准库
- 不许逐行拉取整张表来做连接，不许把未用到的列读进来

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）