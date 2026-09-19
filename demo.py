"""下单到归档的主流程样子（线上演示脚本，输出格式别动）。"""

from orderflow import InvalidTransitionError, Order

o = Order("SO-2026-0912-0042")
print("new:", o.state(), o.allowed_events())
o.pay(19900)
print("paid:", o.state(), o.allowed_events())
o.ship("SF")
o.deliver("收发室-3F")
print("delivered:", o.state(), o.allowed_events())
o.close()
print("closed:", o.state(), "final:", o.is_final())
for step in o.trail():
    print("trail:", step)

b = Order("SO-2026-0913-0007")
b.pay(500)
b.cancel()
print("cancelled:", b.state(), b.allowed_events())
try:
    b.ship("SF")
except InvalidTransitionError as e:
    print("err:", e)
try:
    b.pay(1)
except InvalidTransitionError as e:
    print("err:", e)
try:
    Order("X").can("explode")
except ValueError as e:
    print("err:", e)
