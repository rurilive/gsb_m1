# acx

多模式串匹配，纯标准库，无外部依赖。

## 现状

`acx/multi.py` 提供 `Matcher`，对每个模式串各自在文本里逐位置滑动比较：

- `patterns()`：返回按构造顺序排列的模式串列表
- `find_all(text)`：返回字典，模式串到命中起始下标（升序）的映射
- `find(pattern, text)` / `count(pattern, text)`：单模式查询与计数
- `search(text)`：返回按模式顺序、同模式内升序的 `(pattern, start)` 列表
- `total(text)`：全部模式串的命中总数

## 问题

模式一多就对文本重复扫描，没有跨模式共享的前缀结构，扫描次数随模式
数量线性增长；模式集合越大，重复的前缀比较越多。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_multi.py` 基线保持一致（基线一个字不改）
- 纯标准库，异常继承 `Erro` 基类

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
