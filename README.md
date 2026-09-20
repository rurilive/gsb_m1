# blooms

按层组织的内存表，每层配布隆过滤器，纯标准库，无外部依赖。

## 现状

`blooms/table.py` 提供分层内存表 `MemTable`：

- `MemTable(level_capacity=2, ratio=4, error_rate=0.01)`：`level_capacity` 是第 0 层的条目上限，更深一层上限乘一次 `ratio`，`ratio` 小于 2、`error_rate` 不在 (0, 1) 都直接报错
- `put(key, value)`：写进最新一层，该层超过上限就与下一层合并压实，新层覆盖旧层同名键；受影响层的过滤器当场按新键集重建
- `get(key)`：先逐层问布隆过滤器，说没有的层整层跳过，说可能有才扫该层，未命中返回 None
- `levels()`：各层快照列表，下标即层号，0 最新，返回独立 dict
- `len(t)`：所有层条目总数
- `stats()`：`puts` / `gets` / `hits` / `misses` / `levels`，外加 `bloom_skips`（过滤器拦下的层数）、`bloom_scans` / `bloom_penetrations`（真扫层数）、`bloom_level_error_rates` 与整表 `bloom_estimated_error_rate`
- `BloomFilter(expected_items, error_rate)`：独立过滤器，`add` / `might_contain` / `estimated_false_positive_rate` / `rebuild` / `dump` / `load`；写超建时条目数自动倍增容量并重建
- `t.dump(path)` / `MemTable.load(path)`：整表落盘读回，重启后行为与统计一致

层号越小越新，压实只在写入路径上发生，读取不动数据。没有锁，单线程使用。

## 问题

空查由每层布隆过滤器挡掉：过滤器说某层肯定没有就整层跳过，只有说可能有才扫。

## 运行

```bash
python3 demo.py                          # 压实、逐层查找与过滤器演示
python3 -m unittest discover -s tests -v # 全部测试（基线 + 过滤器）
```

## 实现说明

- 每层一个 `blooms.bloom.BloomFilter`，挂在内部，与层 dict 一一对应，`get` 先问过滤器：说没有整层跳过（计 `bloom_skips`），说可能有才扫该层（计 `bloom_scans`，即穿透）
- `stats()` 另给 `bloom_penetrations`（等同 scans）和 `bloom_level_error_rates`，整表 `bloom_estimated_error_rate` 取各层按自身条目数估算值 (1-e^(-kn/m))^k 的最大者
- 压实合并后，被清空层与接收合并结果的层都按新键集 `rebuild`，旧位数组绝不沿用，杜绝假阴
- 过滤器按建时条目数定容量，写超 `expected_items` 自动倍增容量并按全部已写键重建，误判率拉回目标值
- 落盘为魔数 `BLMF`/`BLMT` + 版本字节 + pickle：过滤器存参数、已写键全集和位数组，`MemTable` 另存各层键值与全部计数；读回逐项对账，行为与统计同落盘前
