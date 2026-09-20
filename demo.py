"""配额池演示。"""
import time

from quota import QuotaExceeded, QuotaPool, ReservationExpired

pool = QuotaPool(100)
pool.acquire(30)
pool.acquire(20)
print("total=%d available=%d used=%d" % (pool.total, pool.available, pool.used))
print("utilisation=%.2f" % pool.utilisation())
try:
    pool.acquire(80)
except QuotaExceeded as exc:
    print("拒绝:", exc)

# 第二段：预留与退还
print()
print("--- 预留 / 按实结算 / 超时回收 ---")
rpool = QuotaPool(100)

# 任务 A 预留 40，跑一半被降级只用 10，剩余 30 按实际消耗退还
a = rpool.reserve(40, ttl=60)
print("预留 A=40 后 available=%d reserved=%d"
      % (rpool.available, rpool.reserved))
print("结算 A 实耗 10，退还=%d" % rpool.settle(a, 10))
print("结算后 used=%d available=%d" % (rpool.used, rpool.available))

# 重试组件和解算器各结算一次：重复结算幂等，不重复退还
b = rpool.reserve(30, ttl=60)
print("重复结算 B：第一次退还=%d，第二次退还=%d"
      % (rpool.settle(b, 25), rpool.settle(b, 25)))

# 退还额不能超过预留量：实耗大于预留直接报错
c = rpool.reserve(20, ttl=60)
try:
    rpool.settle(c, 21)
except ValueError as exc:
    print("拒绝多退:", exc)
print("拒绝后账目不变 reserved=%d available=%d"
      % (rpool.reserved, rpool.available))
rpool.settle(c, 20)

# 申请完再没消息的预留：用注入时钟精确演示超时收回
class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


fake_clock = Clock()
tpool = QuotaPool(50, clock=fake_clock)
d = tpool.reserve(50, ttl=10)
print("预留 D=50 后 available=%d" % tpool.available)
fake_clock.advance(10)
print("超时扫描回收=%d，available=%d"
      % (tpool.reap_expired(), tpool.available))
try:
    tpool.settle(d, 10)
except ReservationExpired as exc:
    print("超时后再结算拒绝:", exc)

# 生产环境用默认时钟 + 后台守护线程定期回收
lpool = QuotaPool(50)
lpool.reserve(50, ttl=0.05)
lpool.start_reaper(interval=0.02)
time.sleep(0.1)
print("后台 reaper 自动回收后 reserved=%d available=%d"
      % (lpool.reserved, lpool.available))
lpool.stop_reaper()
