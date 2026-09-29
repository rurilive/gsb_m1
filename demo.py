"""TimerSet 现状演示。

第一段：注册若干定时器，推进注入时钟，看到期定时器被取走；取消一个之后
不再触发。
第二段：预留的分层时间轮演示位子（见文末注释）。
"""

from tickbox.timers import TimerSet


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def main():
    print("=== 朴素定时器集合 ===")
    c = FakeClock()
    t = TimerSet(clock=c)
    t.add(2, payload="a")
    t.add(4, payload="b")
    doomed = t.add(4, payload="c")
    doomed.cancel()
    print("  注册 3 个定时器，取消 1 个，当前 size=%d" % t.size)
    c.advance(2)
    print("  tick(2) 到期 -> %s" % [h.payload for h in t.tick(2)])
    c.advance(2)
    print("  tick(4) 到期 -> %s" % [h.payload for h in t.tick(4)])
    print("  剩余 size=%d" % t.size)

    # TODO(时间轮改造): 在 tickbox 里补出分层时间轮之后，在这里加一段演示：
    # 用同一注入时钟展示粗粒度轮槽到期时把任务级联下推到细粒度轮、最终在正确
    # tick 触发；对同一定时器改期后旧槽位不再持有它；以及取消后同一 tick 不再
    # 触发，并打印各级任务数与统计口径。


if __name__ == "__main__":
    main()
