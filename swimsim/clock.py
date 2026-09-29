"""可注入、可手动推进的时钟。

协议不读系统墙上时间，只认这里的 tick。心跳超时、怀疑超时、反熵轮次
全部按这一个计数推进，因此换一个时钟就能把整段失败探测复现出来。
"""

from .errors import DefinitionError


class ManualClock:
    """从 start 起、按 step 手动推进的逻辑时钟。"""

    def __init__(self, start=0.0, step=1.0):
        if not isinstance(step, (int, float)) or step <= 0:
            raise DefinitionError("时钟步长必须是正数: %r" % (step,))
        self._now = float(start)
        self._step = float(step)

    @property
    def now(self):
        """当前逻辑时间。"""
        return self._now

    @property
    def step_size(self):
        """每次 advance 推进的步长。"""
        return self._step

    def advance(self, n=1):
        """把时钟向前推 n 步，返回推进后的当前时间。"""
        if not isinstance(n, int) or n < 0:
            raise DefinitionError("推进步数必须是非负整数: %r" % (n,))
        self._now += self._step * n
        return self._now

    def __repr__(self):
        return "<ManualClock now=%r step=%r>" % (self._now, self._step)