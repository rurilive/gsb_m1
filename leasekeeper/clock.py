"""可注入时钟：生产走单调钟，测试用假钟手动拨。

租约的过期判定只信这一条钟，测试里换成 FakeClock 才能把时刻精确拨进
拨出，也可以用 set 拨回过去，专门制造时钟异常的现场。
"""

import threading


class MonotonicClamp:
    """包住任意时钟只报见过的最大值：回拨被钳在原地，单调只增。

    机房切换时 NTP 把钟往回拨，按墙上时间判过期的租约会凭空多活一截。
    把底层钟套进这个钳子，回拨的读数一律按最后见过的最大值报，过期判
    定就再也吃不到回拨。
    """

    def __init__(self, clock):
        self._clock = clock
        self._lock = threading.Lock()
        self._last = None

    def current(self):
        """当前时刻：底层读数与历史最大值取大者。"""
        with self._lock:
            now = float(self._clock())
            if self._last is None or now > self._last:
                self._last = now
            return self._last


class FakeClock:
    """手动推进的假时钟，线程安全。

    current() 读当前时刻，advance(seconds) 往前拨，set(to) 直接拨到
    某个值；set 允许往回拨，用来模拟时钟被回拨的事故现场。
    """

    def __init__(self, start=0.0):
        self._lock = threading.Lock()
        self._now = float(start)

    def current(self):
        """当前时刻。"""
        with self._lock:
            return self._now

    def advance(self, seconds):
        """把时钟往前拨 seconds，返回拨完的时刻。"""
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("advance only moves forward")
        with self._lock:
            self._now += seconds
            return self._now

    def set(self, to):
        """把时钟拨到 to，允许往回拨，返回拨完的时刻。"""
        with self._lock:
            self._now = float(to)
            return self._now
