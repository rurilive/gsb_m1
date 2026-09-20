# quota

平台的资源配额池，纯标准库。

- `quota/pool.py`：`QuotaPool.acquire()`，按预估量申请、申请即扣减
- `tests/test_quota.py`：行为基线
- `demo.py`：额度申请与拒绝演示
