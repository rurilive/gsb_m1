"""Small demo for flowcap.

The first block exercises the shipped CounterLimiter: a few requests are
allowed, then everything after the budget is rejected. The second block is a
placeholder for the sliding window work described in the task.
"""

from flowcap import CounterLimiter


def demo_counter():
    print("== CounterLimiter baseline ==")
    limiter = CounterLimiter(limit=3)
    for i in range(1, 6):
        print("request %d -> %s" % (i, "allow" if limiter.allow() else "reject"))
    print("total seen:", limiter.count)


# TODO(滑动窗口限流改造): 在此补充一轮滑动窗口放行与拒绝的演示，
# 使用注入时钟推进时间，展示窗口随时钟滑动后旧记录过期、新的请求重新放行。


if __name__ == "__main__":
    demo_counter()
