"""指标注册表演示。"""
import json

from metrics import Registry

reg = Registry()
requests = reg.counter("http_requests", ["path", "status"])
requests.inc(path="/home", status="200")
requests.inc(2, path="/home", status="200")
requests.inc(path="/api", status="500")

queue = reg.gauge("queue_depth", ["queue"])
queue.set(3, queue="default")

print(json.dumps(reg.snapshot(), ensure_ascii=False, indent=2))

# 第二段：基数控制演示
# user_id 之类的高基维度打爆上限后，超限序列并入 __overflow__ 兜底桶，
# 看板总量不断；snapshot 的 cardinality 字段暴露被丢写入数与维度采样。
limited = Registry(max_series=3)
by_user = limited.counter("api_calls", ["user_id"])
for i in range(10):
    by_user.inc(user_id=f"user_{i}")
by_user.inc(5, user_id="user_9")

print(json.dumps(limited.snapshot(), ensure_ascii=False, indent=2))

by_user.reset()  # 恢复入口：清空后被丢维度下次写入即回到正常序列
by_user.inc(user_id="user_9")

print(json.dumps(limited.snapshot(), ensure_ascii=False, indent=2))
