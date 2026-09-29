# expirex

一个带上限的字典，纯标准库，无外部依赖。

## 现状

expirex/store.py 提供 LimitedDict：

- LimitedDict(capacity)：按条目数上限建字典
- get(key)：命中返回值，未命中返回 None
- set(key, value)：已有键改值，新键在容量满时先删掉一个键
- delete(key)：删除键，键不存在时什么都不做
- keys() / len() / in：遍历键、条目数与成员判断

删除挑的是当前字典里第一个键，没有淘汰顺序，也没有访问序。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_store.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
