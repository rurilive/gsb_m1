"""可注入的 IO 设备与模型时钟。

引擎里每一次落盘都从设备走账，调用方报出这次占多少 IO 单位。设备
同一时刻只服务一个请求，忙的时候后来的请求排在后面。两种用法：

- charge(): 当前调用方自己用设备，同步等设备空出来，完事把模型时钟
  推到完成时刻，返回完成时刻。前台写、读都走它。
- reserve(): 后台把设备占住一段时间，从设备和时钟里更晚的那一刻起
  算起，只占设备、不推进模型时钟。压缩走它，前台写会因此排队。

模型时钟也可以由调用方用 advance() 直接往前推，测试与验收就靠它
复现同一根时间轴。
"""


class SimDevice:
    """模拟 IO 设备，同时充当模型时钟。

    unit_cost: 一个 IO 单位占设备多长时间。
    """

    def __init__(self, unit_cost=1.0):
        unit_cost = float(unit_cost)
        if unit_cost <= 0:
            raise ValueError("unit_cost must be positive")
        self.unit_cost = unit_cost
        self._now = 0.0
        self._busy_until = 0.0
        self.read_units = 0
        self.write_units = 0
        self.calls = []

    def now(self):
        """当前模型时刻。"""
        return self._now

    @property
    def busy_until(self):
        """设备被占到的时刻。"""
        return self._busy_until

    def free(self):
        """设备现在空着吗。"""
        return self._now >= self._busy_until

    def advance(self, dt=1.0):
        """把模型时钟往前推 dt，返回新时刻。"""
        if dt < 0:
            raise ValueError("dt must be non-negative")
        self._now += dt
        return self._now

    def charge(self, kind, units):
        """自己用设备，返回完成时刻。

        kind 是 "read" 或 "write"，units 是这次占用的 IO 单位数。
        设备忙则排队等，等到的那一刻就是这次调用的开始，时间跟着走到
        完成时刻。
        """
        end = self._serve("charge", kind, units)
        if end > self._now:
            self._now = end
        return end

    def reserve(self, kind, units):
        """后台占住设备，返回占用到哪个时刻。

        只把设备往后占，不动模型时钟：前台请求碰上这段占用就得排队。
        """
        return self._serve("reserve", kind, units)

    def _serve(self, mode, kind, units):
        if kind not in ("read", "write"):
            raise ValueError("kind must be read or write")
        if units < 0:
            raise ValueError("units must be non-negative")
        start = self._now if self._now >= self._busy_until else self._busy_until
        end = start + units * self.unit_cost
        self._busy_until = end
        self.calls.append((mode, kind, units, start, end))
        if kind == "read":
            self.read_units += units
        else:
            self.write_units += units
        return end

    def __repr__(self):
        return "SimDevice(now=%.1f, busy=%.1f, r=%d, w=%d)" % (
            self._now, self._busy_until, self.read_units, self.write_units)
