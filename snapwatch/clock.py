"""可手动推进的时钟，测试和演示拿它把时间片卡准。"""


class ManualClock:
    """秒为单位的挂钟替身，和文件 mtime 在同一根时间轴上。"""

    def __init__(self, now=0.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)
        return self.now
