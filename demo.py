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
