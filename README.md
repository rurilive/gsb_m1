# quota

平台的资源配额池，纯标准库。

- `quota/pool.py`：`QuotaPool`，`acquire()` 按预估量申请即扣减；`reserve()`/`settle()` 预留后按实际消耗退还差额；`reap_expired()`/`start_reaper()` 超时自动回收
- `tests/test_quota.py`：行为基线
- `tests/test_reserve.py`：重复结算、部分消耗、超时回收与并发对撞
- `demo.py`：额度申请与拒绝演示

## 实现说明

1. 每条预留存 `amount/deadline/state(active/settled/expired)`，额度冻结在 `reserved`，账目恒等式 `used + reserved + available == total`。
2. `reserve(amount, ttl)` 先扫过期再判容量，返回带 `id/deadline` 的不透明 `Reservation` 凭证。
3. `settle(reservation, consumed)` 按实耗结算，退还 `amount-consumed`，实耗计入 `used`。
4. `consumed > amount` 直接 `ValueError`，账目不动，绝不凭空多退。
5. 重复结算幂等：已 `settled` 的凭证再结算返回 0，不再动账。
6. 超时判定为注入时钟的 `deadline <= now`，到期预留全额回收、状态置 `expired`，再结算抛 `ReservationExpired`。
7. `reserve`/`settle` 入口惰性回收，`reap_expired()` 可显式扫描，`start_reaper()` 提供后台守护线程兜底。
8. 所有账目变更在同一把 `threading.Lock` 下原子完成，状态迁移只发生一次。
9. 因此结算与回收并发对撞时，谁先持锁谁生效，同一笔额度不会既退还又回收。
