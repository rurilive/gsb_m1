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
print("\n--- 基数控制 ---")
limited = Registry(max_series=3)
api = limited.counter("api_calls", ["path", "user_id"])
api.inc(path="/home", user_id="u1")
api.inc(path="/home", user_id="u2")
api.inc(path="/home", user_id="u3")
# user_id 爆炸：超限维度不丢数据，并入 __overflow__ 兜底桶
for i in range(1000):
    api.inc(path="/home", user_id=f"attacker-{i}")

snap = api.snapshot()
card = dict(snap["cardinality"], dropped_keys=snap["cardinality"]["dropped_keys"][:3])
print(json.dumps(card, ensure_ascii=False, indent=2))
print("series 条数:", len(snap["series"]), "（含兜底桶，而非 1003 条）")

# 序列数回落后，被打掉的维度自动恢复为独立序列
api.reset()
api.inc(path="/home", user_id="attacker-0")
print("恢复后 attacker-0:", api.value(path="/home", user_id="attacker-0"))

# 导出侧限流：series_budget 约束单次导出的总序列数
export = limited.snapshot(series_budget=2)
for m in export["metrics"]:
    m.pop("cardinality", None)
print(json.dumps(export, ensure_ascii=False, indent=2))
