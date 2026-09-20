"""时间轮演示：手动推进时钟，观察任务按期进入就绪队列。"""

from timewheel import TimeWheel
from timewheel.clock import ManualClock

clock = ManualClock(1000.0)
wheel = TimeWheel(slots=32, tick=1.0, clock=clock)

wheel.add(2, "flush-metrics")
wheel.add(3, "rotate-log")
cancelled = wheel.add(5, "temp-cleanup")
wheel.add(7, "heartbeat")
print("cancel temp-cleanup ->", cancelled.cancel())

for target in (1002, 1003, 1005, 1007):
    clock.advance(target - clock.t)
    wheel.advance(target)
    print("now=%d ready=%s" % (target, wheel.due()))
