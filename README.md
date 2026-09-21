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

## 运行

```bash
python3 demo.py                           # 计数、分片账本、落盘读回
python3 -m unittest discover -s tests     # 行为基线
```

## 目标

见任务描述。约束：现有行为与 `tests/` 基线保持不变（基线一个字不改），
纯标准库。
