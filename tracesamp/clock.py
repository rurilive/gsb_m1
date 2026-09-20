"""可手动推进的假时钟：让窗口滚动、补充这些动作在测试和演示里能精确对上。"""


class ManualClock:
    """调用一次读一次当前时刻；只有 advance 会让它往前走。"""

    def __init__(self, start=0.0):
        self._now = float(start)

    def __call__(self):
        return self._now

    def advance(self, seconds):
        """把时钟往前拨 seconds 秒。"""
        if seconds < 0:
            raise ValueError("seconds must be >= 0")
        self._now += float(seconds)
        return self._now
