"""注册表层：计数器与直方图的可变状态收在 Registry 实例里。

只负责登记与读写，不做统计、不做格式化；取数通过 snapshot()
转成交给口径层的原始视图。
"""

from __future__ import annotations

from metrio.snapshot import Snapshot, build_snapshot


class Registry:
    """进程内指标注册表。counter 与 histogram 命名空间相互独立。"""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}
        self._counter_order: list[str] = []
        self._histogram_order: list[str] = []

    def inc(self, name: str, n: int = 1) -> int:
        """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""
        if not isinstance(n, int):
            raise TypeError("inc expects an int n, got %r" % (n,))
        if name not in self._counters:
            self._counters[name] = 0
            self._counter_order.append(name)
        self._counters[name] += n
        return self._counters[name]

    def counter_value(self, name: str, default: int = 0) -> int:
        """读计数器当前值，没注册过返回 default。"""
        return self._counters.get(name, default)

    def histogram(self, name: str) -> None:
        """注册一个空直方图（后面 observe 往里灌样本）。"""
        if name not in self._histograms:
            self._histograms[name] = []
            self._histogram_order.append(name)

    def observe(self, name: str, value: float) -> None:
        """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""
        if name not in self._histograms:
            self._histograms[name] = []
            self._histogram_order.append(name)
        self._histograms[name].append(value)

    def snapshot(self) -> Snapshot:
        """按注册顺序导出当前状态的不可变统计快照。"""
        return build_snapshot(
            [(name, self._counters[name]) for name in self._counter_order],
            [(name, list(self._histograms[name])) for name in self._histogram_order],
        )

    def reset(self) -> None:
        """清空全部指标（进程内测试用）。"""
        self._counters.clear()
        self._histograms.clear()
        del self._counter_order[:]
        del self._histogram_order[:]
