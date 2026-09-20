"""给监控后台导指标的样子（线上 demo，输出格式别动）。"""

from metrio import counter_value, export_json, export_prom, histogram, inc, observe, render_text, reset

reset()

inc("http.requests")
inc("http.requests")
inc("http.requests", 40)
inc("cache.hits", 7)
inc("cache.miss")
inc("gc.pause", -1)

print("requests now:", counter_value("http.requests"))

histogram("latency.ms")
observe("latency.ms", 12.0)
observe("latency.ms", 31.5)
observe("latency.ms", 7.25)
observe("latency.ms", 120.0)
observe("latency.ms", 44.5)
observe("size.kb", 3.5)
observe("size.kb", 8.0)
observe("size.kb", 2.25)

print("== text ==")
print(render_text())
print("== json ==")
print(export_json())
print("== prom ==")
print(export_prom())
