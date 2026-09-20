"""配额池演示。"""
from quota import QuotaExceeded, QuotaPool

pool = QuotaPool(100)
pool.acquire(30)
pool.acquire(20)
print("total=%d available=%d used=%d" % (pool.total, pool.available, pool.used))
print("utilisation=%.2f" % pool.utilisation())
try:
    pool.acquire(80)
except QuotaExceeded as exc:
    print("拒绝:", exc)

# 第二段：预留与退还演示（留给实现者补）
now = [1000.0]
pool2 = QuotaPool(100, clock=lambda: now[0], reservation_timeout=30)

rid = pool2.reserve(40)
print("预留 40: available=%d" % pool2.available)
refunded = pool2.settle(rid, 15)  # 实际只用 15，退 25
print("结算实际用量 15，退还 %d: used=%d available=%d" % (refunded, pool2.used, pool2.available))
print("重复结算退还 %d（幂等，不退超）" % pool2.settle(rid, 15))

rid2 = pool2.reserve(50)
now[0] += 60  # 任务再没消息，预留超时
print("超时收回 %s: used=%d available=%d" % (pool2.reclaim_expired(), pool2.used, pool2.available))
