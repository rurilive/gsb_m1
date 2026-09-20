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

## 实现说明

- 每层挂一个 `blooms.bloom.BloomFilter`（SHA1 双哈希），容量按该层条目上限建；`get` 先问过滤器，说没有就 `filter_skips` 加一整层跳过，说可能有才穿透扫 dict 计 `filter_probes`，命中提前停。
- 压实合并后源层与目标层的旧位数组都作废：源层重置、目标层用合并后键集全量重建，键集变了绝不沿用旧数组，杜绝假阴。
- `stats()` 另报目标 `error_rate` 和表级估算误判率（各层按当前条目数套 `(1-e^(-kn/m))^k` 后的联合值），每层明细在 `filter_stats()`；实际条目超容量时 `saturated=True`，`BloomFilter.rebuild(keys)` 容量翻倍重建把误判率压回来，`put` 路径自动触发。
- 落盘为单个 JSON：magic/version、构造参数、各层 `[key, value]` 列表、计数器、每层过滤器的参数与十六进制位数组；`load` 校验位数组与参数一致、过滤器条目数与层内容一致，读回后行为与统计与存盘前相同。
