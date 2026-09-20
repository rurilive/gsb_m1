# quota

平台的资源配额池，纯标准库。

- `quota/pool.py`：`QuotaPool.acquire()`，按预估量申请、申请即扣减
- `tests/test_quota.py`：行为基线
- `demo.py`：额度申请与拒绝演示

## 实现说明

- 预留：`reserve(amount)` 扣减额度并记录 `{预留量, 创建时间, 状态}`，返回预留号
- 结算：`settle(预留号, 实际用量)` 退还「预留量 - 实际用量」，状态置为 settled
- 幂等：已结算或已过期的预留再结算返回 0，不重复退款，重复结算不退超
- 上限：实际用量超过预留量抛 ValueError，账目不变，宁可报错也不多退
- 超时：开放预留存活超过 `reservation_timeout` 即判过期，`reclaim_expired` 全额收回
- 惰性回收：`acquire`/`reserve`/`settle` 入口先扫描过期预留，无需后台线程
- 时钟：`clock` 可注入，默认 `time.monotonic`，测试用假时钟精确断言超时边界
- 并发：所有账目操作共用一把锁，结算与超时回收在锁内串行，先到者生效、后到者空操作
