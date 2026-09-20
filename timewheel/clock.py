"""可手动拨动的假时钟，测试与演示用。"""


class ManualClock:
    """手动推进的单调时钟：调用实例返回当前时刻。"""

    def __init__(self, start=0.0):
        self.t = float(start)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds
