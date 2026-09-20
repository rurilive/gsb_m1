# idxstore

文档检索服务的倒排索引，纯标准库。

- `idxstore/store.py`：内存正排 + 倒排，攒够 `snapshot_every` 次变更就整份全量落盘
- `tests/test_store.py`：行为基线
- `demo.py`：写入、检索、落盘、重载演示

## 实现说明

- 日志格式：`index.wal.jsonl`，每行一条 JSON `{seq, op, doc_id, text?, crc}`，crc 是其余字段的 CRC32
- 写顺序：先追加日志并 fsync，再改内存；同一把锁包住两步，日志顺序即内存生效顺序
- 快照对齐：快照记录已覆盖的最大 seq，恢复时只重放 seq 更大的日志，旧记录直接跳过
- 裁剪时机：快照经临时文件 + rename 原子落盘（含目录 fsync）成功后整份删除 WAL，下次变更重建
- 坏记录：逐行解析，JSON 残缺或 crc 不符即视为掉电撕写的尾部，停止重放、截断尾部，不抛异常
