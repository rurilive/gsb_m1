"""渲染层：同一份 Snapshot -> 三种字节级稳定的文本输出。

这里只决定"字段顺序和排版"，不再各算一遍统计。字段序仍是下游契约：
JSON 为 name,count,sum,avg,min,max,p50,p95,p999；prom 为
quantile 行在前、_count/_sum 在后（空直方图无 quantile 行）。
"""

from __future__ import annotations

import json

from metrio.snapshot import HistogramSnapshot, Snapshot


def render_text(snapshot: Snapshot) -> str:
    """人看的文本导出。空注册表返回空串。"""
    lines: list[str] = []
    if snapshot.counters:
        lines.append("counters:")
        for counter in snapshot.counters:
            lines.append("  %s = %d" % (counter.name, counter.value))
    if snapshot.histograms:
        lines.append("histograms:")
        for histo in snapshot.histograms:
            lines.append(
                "  %s n=%d avg=%.2f min=%.2f max=%.2f p50=%.2f p95=%.2f"
                % (
                    histo.name,
                    histo.count,
                    histo.avg,
                    histo.min,
                    histo.max,
                    histo.p50,
                    histo.p95,
                )
            )
    return "\n".join(lines)


def export_json(snapshot: Snapshot) -> str:
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""
    doc: dict[str, list] = {"counters": [], "histograms": []}
    for counter in snapshot.counters:
        doc["counters"].append({"name": counter.name, "value": counter.value})
    for histo in snapshot.histograms:
        doc["histograms"].append(
            {
                "name": histo.name,
                "count": histo.count,
                "sum": histo.sum,
                "avg": histo.avg,
                "min": histo.min,
                "max": histo.max,
                "p50": histo.p50,
                "p95": histo.p95,
                "p999": histo.p999,
            }
        )
    return json.dumps(doc)


def _prom_number(value: float) -> str:
    """prom 风格的数字（%g），和 text/json 的 %.2f 不是一套（历史如此）。"""
    return "%g" % value


def _prom_histogram_lines(histo: HistogramSnapshot) -> list[str]:
    lines = ["# TYPE %s summary" % histo.name]
    if histo.count > 0:
        lines.append('%s{quantile="0.5"} %s' % (histo.name, _prom_number(histo.p50)))
        lines.append('%s{quantile="0.95"} %s' % (histo.name, _prom_number(histo.p95)))
        lines.append(
            '%s{quantile="0.999"} %s' % (histo.name, _prom_number(histo.p999))
        )
    lines.append("%s_count %d" % (histo.name, histo.count))
    lines.append("%s_sum %s" % (histo.name, _prom_number(histo.sum)))
    return lines


def export_prom(snapshot: Snapshot) -> str:
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""
    out: list[str] = []
    for counter in snapshot.counters:
        out.append("# TYPE %s counter" % counter.name)
        out.append("%s %d" % (counter.name, counter.value))
    for histo in snapshot.histograms:
        out.extend(_prom_histogram_lines(histo))
    return "\n".join(out)
