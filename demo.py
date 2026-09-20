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

# 第二段：基数控制演示（留给实现者补）
