# merkletool

对一份有序数据求指纹的小工具，纯标准库，无外部依赖。

## 现状

merkletool/hash.py 提供三个函数：

- hash_bytes(data)：对一段字节求 SHA-256，返回 64 位小写十六进制
- hash_text(text)：按 UTF-8 对文本求摘要
- naive_root(leaves)：把整份列表逐条串成一条字节串，整体求一次摘要

没有分层结构，没有父子关系，改一个条目就把整份数据从头重算，
也拿不出任何能单独交给别人校验的凭据。

## 问题

单层全量哈希无法增量更新，改一个叶子要重算全部；无法为某个叶子
生成可独立校验的包含证明；无法证明一段连续区间没有被改动；每次
变更都失去与上一版的可比性，也说不清根对某个叶子的依赖路径。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_hash.py 基线一致（基线一个字不改）
- 新行为另开 tests/test_merkle.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
