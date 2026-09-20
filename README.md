# idxstore

文档检索服务的倒排索引，纯标准库。

- `idxstore/store.py`：内存正排 + 倒排，攒够 `snapshot_every` 次变更就整份全量落盘
- `tests/test_store.py`：行为基线
- `demo.py`：写入、检索、落盘、重载演示
