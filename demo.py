"""连接池基本用法演示（线上运维巡检用的那套）。"""

import threading

from netpool.pool import ConnectionPool

pool = ConnectionPool(max_size=4, borrow_timeout=1.0)

print("=== 单线程借还 ===")
conns = [pool.borrow() for _ in range(3)]
print("borrowed:", conns)
print("stats:", pool.stats())
for c in conns:
    pool.return_conn(c)
print("after return:", pool.stats())

print("\n=== 并发借还（4 线程 x 50 轮） ===")
errors = []


def worker(n):
    try:
        for i in range(50):
            c = pool.borrow()
            c.healthy = c.healthy  # 模拟使用
            pool.return_conn(c)
    except Exception as e:  # noqa: BLE001
        errors.append("worker-%d: %r" % (n, e))


threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("errors:", errors if errors else "none")
print("stats:", pool.stats())
print("created 总数（含反复借还，应 <= max_size）:", pool.stats()["created"])
