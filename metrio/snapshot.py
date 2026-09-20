"""统计口径层：把注册表当前状态收敛成不可变快照。

所有"排序 / 求和 / 分位"的口径只在这里实现一次，三种导出共用，
快照本身不含任何格式化逻辑，统计口径可独立单测。

分位数统一为最近秩法（整数运算）：升序样本中第 ceil(p*n/100) 个，
1 起数，端点夹紧到 [1, n]；空表口径为 0.0。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CounterSnapshot:
    """单个计数器的快照。"""

    name: str
    value: int


@dataclass(frozen=True)
class HistogramSnapshot:
    """单个直方图的统计快照。count=0 时除 name/count/sum 外均为 0.0。"""

    name: str
    count: int
    sum: float
    avg: float
    min: float
    max: float
    p50: float
    p95: float
    p999: float


@dataclass(frozen=True)
class Snapshot:
    """整注册表的不可变快照；各条目按注册先后排列。"""

    counters: list[CounterSnapshot]
    histograms: list[HistogramSnapshot]


def percentile(sorted_values: list[float], percentile_: int) -> float:
    """最近秩法分位数。sorted_values 必须已升序，空表返回 0.0。"""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    rank = (percentile_ * n + 99) // 100
    if rank < 1:
        rank = 1
    if rank > n:
        rank = n
    return sorted_values[rank - 1]


def histogram_snapshot(name: str, samples: list[float]) -> HistogramSnapshot:
    """从一批原始样本算出单个直方图快照（样本顺序不影响结果）。"""
    ordered = sorted(samples)
    count = len(ordered)
    total = float(sum(ordered))
    avg = total / count if count > 0 else 0.0
    minimum = ordered[0] if count > 0 else 0.0
    maximum = ordered[count - 1] if count > 0 else 0.0
    return HistogramSnapshot(
        name=name,
        count=count,
        sum=total,
        avg=avg,
        min=minimum,
        max=maximum,
        p50=percentile(ordered, 50),
        p95=percentile(ordered, 95),
        p999=percentile(ordered, 999),
    )


def build_snapshot(
    counters: list[tuple[str, int]],
    histograms: list[tuple[str, list[float]]],
) -> Snapshot:
    """按注册顺序把计数器与直方图原始状态构造成快照。"""
    return Snapshot(
        counters=[CounterSnapshot(name, value) for name, value in counters],
        histograms=[
            histogram_snapshot(name, samples) for name, samples in histograms
        ],
    )
