# blooms

按层组织的内存表，纯标准库，无外部依赖。包名叫 blooms，眼下里面一个布隆过滤器都没有。

## 现状

`blooms/table.py` 提供分层内存表 `MemTable`：

- `MemTable(level_capacity=2, ratio=4)`：`level_capacity` 是第 0 层的条目上限，更深一层上限乘一次 `ratio`，`ratio` 小于 2 直接报错
- `put(key, value)`：写进最新一层，该层超过上限就与下一层合并压实，新层覆盖旧层同名键
- `get(key)`：从新到旧逐层查找，未命中返回 None
- `levels()`：各层快照列表，下标即层号，0 最新，返回独立 dict
- `len(t)`：所有层条目总数
- `stats()`：`puts` / `gets` / `hits` / `misses` / `levels` 计数快照

层号越小越新，压实只在写入路径上发生，读取不动数据。没有锁，单线程使用。

## 问题

查一个不存在的键要逐层翻遍，层越压越深，线上绝大多数查询又都是这种空查，白白扫一遍。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_table.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 写入压实与逐层查找演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
