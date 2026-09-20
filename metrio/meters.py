"""metrio.meters：进程内计数器/直方图收集与文本导出。

结构：Registry 持有注册表实例状态，模块级函数是默认实例的薄壳；
导出统一走「快照 → 渲染」管线，统计口径只在快照里算一次。
导出格式是稳定契约，下游有解析器按字段顺序在抓，别动输出。
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

__all__ = [
    "REGISTRY",
    "Registry",
    "Snapshot",
    "inc",
    "counter_value",
    "histogram",
    "observe",
    "render_text",
    "export_json",
    "export_prom",
    "reset",
]


def _percentile(sorted_vals: List[float], p: int) -> float:
    # 最近秩法：第 ceil(p*n/100) 个（1 起数），越界夹回 [1, n]。空表给 0.0。
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    k = (p * n + 99) // 100
    k = max(1, min(k, n))
    return sorted_vals[k - 1]


@dataclass(frozen=True)
class CounterSample:
    name: str
    value: int


@dataclass(frozen=True)
class HistogramStats:
    """一个直方图的统计口径：所有导出格式共用这一份。"""

    name: str
    count: int
    total: float
    avg: float
    min: float
    max: float
    p50: float
    p95: float
    p999: float


@dataclass(frozen=True)
class Snapshot:
    """某一时刻全部指标的只读快照，渲染函数的输入。"""

    counters: Tuple[CounterSample, ...]
    histograms: Tuple[HistogramStats, ...]


def _histogram_stats(name: str, values: List[float]) -> HistogramStats:
    vals = sorted(values)
    n = len(vals)
    total = float(sum(vals))
    avg = total / n if n > 0 else 0.0
    mn = vals[0] if n > 0 else 0.0
    mx = vals[n - 1] if n > 0 else 0.0
    return HistogramStats(
        name=name,
        count=n,
        total=total,
        avg=avg,
        min=mn,
        max=mx,
        p50=_percentile(vals, 50),
        p95=_percentile(vals, 95),
        p999=_percentile(vals, 999),
    )


class Registry:
    """指标注册表：计数器/直方图的实例状态与采集操作。"""

    def __init__(self) -> None:
        self.state: Dict[str, Any] = {
            "counters": {},
            "histos": {},
            "order_c": [],
            "order_h": [],
        }

    def inc(self, name: str, n: int = 1) -> int:
        """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""
        if not isinstance(n, int):
            raise TypeError("inc expects an int n, got %r" % (n,))
        cs = self.state["counters"]
        if name not in cs:
            cs[name] = 0
            self.state["order_c"].append(name)
        cs[name] = cs[name] + n
        return cs[name]

    def counter_value(self, name: str, default: int = 0) -> int:
        """读计数器当前值，没注册过返回 default。"""
        cs = self.state["counters"]
        if name in cs:
            return cs[name]
        return default

    def histogram(self, name: str) -> None:
        """注册一个空直方图（后面 observe 往里灌样本）。"""
        hs = self.state["histos"]
        if name not in hs:
            hs[name] = []
            self.state["order_h"].append(name)

    def observe(self, name: str, value: float) -> None:
        """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""
        hs = self.state["histos"]
        if name not in hs:
            hs[name] = []
            self.state["order_h"].append(name)
        hs[name].append(value)

    def reset(self) -> None:
        """清空全部指标（进程内测试用）。原地清空，REGISTRY 别名不失效。"""
        self.state["counters"].clear()
        self.state["histos"].clear()
        del self.state["order_c"][:]
        del self.state["order_h"][:]

    def snapshot(self) -> Snapshot:
        """按注册顺序取一份统计快照，供各导出格式渲染。"""
        counters = tuple(
            CounterSample(name, self.state["counters"][name])
            for name in self.state["order_c"]
        )
        histograms = tuple(
            _histogram_stats(name, self.state["histos"][name])
            for name in self.state["order_h"]
        )
        return Snapshot(counters=counters, histograms=histograms)


def _render_text(snap: Snapshot) -> str:
    lines = []
    if snap.counters:
        lines.append("counters:")
        for c in snap.counters:
            lines.append("  %s = %d" % (c.name, c.value))
    if snap.histograms:
        lines.append("histograms:")
        for h in snap.histograms:
            lines.append(
                "  %s n=%d avg=%.2f min=%.2f max=%.2f p50=%.2f p95=%.2f"
                % (h.name, h.count, h.avg, h.min, h.max, h.p50, h.p95)
            )
    return "\n".join(lines)


def _render_json(snap: Snapshot) -> str:
    # 字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）
    doc: Dict[str, Any] = {"counters": [], "histograms": []}
    for c in snap.counters:
        doc["counters"].append({"name": c.name, "value": c.value})
    for h in snap.histograms:
        doc["histograms"].append(
            {
                "name": h.name,
                "count": h.count,
                "sum": h.total,
                "avg": h.avg,
                "min": h.min,
                "max": h.max,
                "p50": h.p50,
                "p95": h.p95,
                "p999": h.p999,
            }
        )
    return json.dumps(doc)


def _g(v: float) -> str:
    # prom 风格的数字（%g），和 text/json 的 %.2f 不是一套（历史如此）
    return "%g" % v


def _render_prom(snap: Snapshot) -> str:
    # 字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）
    out = []
    for c in snap.counters:
        out.append("# TYPE %s counter" % c.name)
        out.append("%s %d" % (c.name, c.value))
    for h in snap.histograms:
        out.append("# TYPE %s summary" % h.name)
        if h.count > 0:
            out.append('%s{quantile="0.5"} %s' % (h.name, _g(float(h.p50))))
            out.append('%s{quantile="0.95"} %s' % (h.name, _g(float(h.p95))))
            out.append('%s{quantile="0.999"} %s' % (h.name, _g(float(h.p999))))
        out.append("%s_count %d" % (h.name, h.count))
        out.append("%s_sum %s" % (h.name, _g(h.total)))
    return "\n".join(out)


# ---- 默认实例与模块级薄壳（保持原有模块级 API 不变）----
_DEFAULT = Registry()

# 全进程默认注册表的兼容别名（历史导出，别在别处直接改）
REGISTRY = _DEFAULT.state


def inc(name: str, n: int = 1) -> int:
    """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""
    return _DEFAULT.inc(name, n)


def counter_value(name: str, default: int = 0) -> int:
    """读计数器当前值，没注册过返回 default。"""
    return _DEFAULT.counter_value(name, default)


def histogram(name: str) -> None:
    """注册一个空直方图（后面 observe 往里灌样本）。"""
    _DEFAULT.histogram(name)


def observe(name: str, value: float) -> None:
    """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""
    _DEFAULT.observe(name, value)


def render_text() -> str:
    """人看的文本导出。空注册表返回空串。"""
    return _render_text(_DEFAULT.snapshot())


def export_json() -> str:
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""
    return _render_json(_DEFAULT.snapshot())


def export_prom() -> str:
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""
    return _render_prom(_DEFAULT.snapshot())


def reset() -> None:
    """清空全部指标（进程内测试用）。"""
    _DEFAULT.reset()
