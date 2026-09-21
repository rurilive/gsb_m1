"""监控后台报表渲染的样子（线上 demo，输出格式别动）。"""

from texttbl import Table

T1 = Table(["service", "qps", "p95"], style="ascii")
(
    T1.add_row("gateway", "18230", "12.4")
    .add_row("auth", "4310", "3.1")
    .add_row("billing", "872", "55.9")
)

T2 = Table(["service", "qps", "p95"], style="light")
T2.add_row("gateway", "18230", "12.4").add_row("auth", "4310", "3.1")

T3 = Table(["service", "qps", "p95"], style="heavy")
T3.add_row("gateway", "18230", "12.4")

T4 = Table(["service", "qps", "p95"], style="markdown")
T4.add_row("gateway", "18230", "12.4").add_row("auth", "4310", "3.1")

T5 = Table(["module", "note"], style="ascii", wrap=16)
T5.add_row("scheduler", "runs every five minutes and picks up pending jobs")
T5.add_row("cache", "evicts on the hour")

print("== ascii ==")
print(T1.render())
print("== light ==")
print(T2.render())
print("== heavy ==")
print(T3.render())
print("== markdown ==")
print(T4.render())
print("== wrapped ==")
print(T5.render())
