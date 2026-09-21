# dedupkit

分片埋点链路的去重计数库，纯标准库，无外部依赖。

## 模块

- `dedupkit/exact.py`：`ExactCounter`，用 set 存 key。`add(key)` 报告
  这次是不是新 key，`count()` 给精确的不同 key 数，`keys()` 给一份快照，
  `in` 判断是否出现过，`reset()` 清空。单次操作线程安全。
- `dedupkit/ledger.py`：`Ledger`，按分片记账。`add(shard, key)` 在分片
  不存在时新建（分片名必须是 str），`count(shard)` / `keys(shard)` 看单片的
  数，`total()` 把各片的 count 直接相加，跨片重复的 key 会被重复计入，
  `names()` 给排好序的分片名。
- `dedupkit/codec.py`：`save(ledger, path)` 与 `load(path)`，JSON 格式，
  顶层带 `fmt` 格式号（当前 1）。key 按类型标签编码，str、int、bool、
  bytes、tuple、None 都能往返；同一份账本落盘两次字节一致。文件缺失抛
  `FileNotFoundError`，内容不合法抛 `ValueError`。
- `dedupkit/sketch.py`：`BucketSketch(bits, seed)`，2**bits 个定容桶
  （默认 bits=12，约 4KB），HyperLogLog 风格的分桶基数估算；`merge`
  返回并集的新估算器。codec 以 `save_sketch` / `fmt 2` 落盘，`load`
  按版本号分发，fmt 1 老文件照旧返回 `Ledger`。

## 运行

```bash
python3 demo.py                           # 计数、分片账本、落盘读回
python3 -m unittest discover -s tests     # 行为基线
```

## 目标

见任务描述。约束：现有行为与 `tests/` 基线保持不变（基线一个字不改），
纯标准库。

## 实现说明

- key 先经 codec 的类型标签编码再 blake2b 散列（带 seed 域分隔），桶号取低 bits 位，桶值存剩余位前导零数 +1。
- `count()` 用调和均值（小 m 修正系数）；空桶较多时走线性计数，2.5m–4m 区间线性混合，避免小基数起飞和切换区冒尖。
- `merge` 逐桶取 max，等价于把并集数据从零重建，满足交换律、结合律、幂等；参数（bits/seed）不一致抛 `ValueError`。
- 桶位是固定长 `bytearray`，内存只随 bits 变，不随 key 数涨。
- fmt 2 文档为 `{"fmt":2,"kind":"sketch","sketch":{bits,seed,registers(base64)}}`，未知字段忽略；fmt 1 读回后可把 key 灌进估算器继续合并。
