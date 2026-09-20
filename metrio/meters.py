"""metrio.meters：进程内计数器/直方图收集与文本导出。

2019 年排障时随手写的，全进程共用一份注册表。导出格式是稳定契约，
下游有解析器按字段顺序在抓，别动输出。
"""

import json

# ---- 全进程唯一的指标注册表（模块级可变变量，历史原因，别在别处直接改）----
REGISTRY = {"counters": {}, "histos": {}, "order_c": [], "order_h": []}


def inc(name, n=1):
    """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""
    if not isinstance(n, int):
        raise TypeError("inc expects an int n, got %r" % (n,))
    cs = REGISTRY["counters"]
    if name not in cs:
        cs[name] = 0
        REGISTRY["order_c"].append(name)
    cs[name] = cs[name] + n
    return cs[name]


def counter_value(name, default=0):
    """读计数器当前值，没注册过返回 default。"""
    cs = REGISTRY["counters"]
    if name in cs:
        return cs[name]
    return default


def histogram(name):
    """注册一个空直方图（后面 observe 往里灌样本）。"""
    hs = REGISTRY["histos"]
    if name not in hs:
        hs[name] = []
        REGISTRY["order_h"].append(name)


def observe(name, value):
    """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""
    hs = REGISTRY["histos"]
    if name not in hs:
        hs[name] = []
        REGISTRY["order_h"].append(name)
    hs[name].append(value)


def _pctl_for_text(vals, p):
    # 最近秩法：第 ceil(p*n/100) 个（1 起数）。空表给 0.0。
    n = len(vals)
    if n == 0:
        return 0.0
    k = (p * n + 99) // 100
    if k < 1:
        k = 1
    if k > n:
        k = n
    return vals[k - 1]


def _pctl_for_json(vals, p):
    import math
    n = len(vals)
    if n == 0:
        return 0.0
    k = int(math.ceil(n * p / 100.0))
    if k < 1:
        k = 1
    if k > n:
        k = n
    return vals[k - 1]


def render_text():
    """人看的文本导出。空注册表返回空串。"""
    lines = []
    cs = REGISTRY["counters"]
    if len(REGISTRY["order_c"]) > 0:
        lines.append("counters:")
        for name in REGISTRY["order_c"]:
            lines.append("  %s = %d" % (name, cs[name]))
    hs = REGISTRY["histos"]
    if len(REGISTRY["order_h"]) > 0:
        lines.append("histograms:")
        for name in REGISTRY["order_h"]:
            vals = sorted(hs[name])
            n = len(vals)
            total = 0.0
            for v in vals:
                total = total + v
            avg = 0.0
            if n > 0:
                avg = total / n
            mn = 0.0
            mx = 0.0
            if n > 0:
                mn = vals[0]
                mx = vals[n - 1]
            p50 = _pctl_for_text(vals, 50)
            p95 = _pctl_for_text(vals, 95)
            lines.append(
                "  %s n=%d avg=%.2f min=%.2f max=%.2f p50=%.2f p95=%.2f"
                % (name, n, avg, mn, mx, p50, p95)
            )
    return "\n".join(lines)


def export_json():
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""
    doc = {"counters": [], "histograms": []}
    cs = REGISTRY["counters"]
    for name in REGISTRY["order_c"]:
        doc["counters"].append({"name": name, "value": cs[name]})
    hs = REGISTRY["histos"]
    for name in REGISTRY["order_h"]:
        vals = sorted(hs[name])
        n = len(vals)
        s = float(sum(vals))
        avg = 0.0
        if n > 0:
            avg = s / n
        mn = 0.0
        mx = 0.0
        if n > 0:
            mn = vals[0]
            mx = vals[n - 1]
        doc["histograms"].append(
            {
                "name": name,
                "count": n,
                "sum": s,
                "avg": avg,
                "min": mn,
                "max": mx,
                "p50": _pctl_for_json(vals, 50),
                "p95": _pctl_for_json(vals, 95),
                "p999": _pctl_for_json(vals, 999),
            }
        )
    return json.dumps(doc)


def _g(v):
    # prom 风格的数字（%g），和 text/json 的 %.2f 不是一套（历史如此）
    return "%g" % v


def export_prom():
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""
    out = []
    cs = REGISTRY["counters"]
    for name in REGISTRY["order_c"]:
        out.append("# TYPE %s counter" % name)
        out.append("%s %d" % (name, cs[name]))
    hs = REGISTRY["histos"]
    for name in REGISTRY["order_h"]:
        vals = sorted(hs[name])
        n = len(vals)
        out.append("# TYPE %s summary" % name)
        if n > 0:
            i50 = (50 * n + 99) // 100 - 1
            i95 = (95 * n + 99) // 100 - 1
            i999 = (999 * n + 99) // 100 - 1
            if i50 < 0:
                i50 = 0
            if i50 > n - 1:
                i50 = n - 1
            if i95 < 0:
                i95 = 0
            if i95 > n - 1:
                i95 = n - 1
            if i999 < 0:
                i999 = 0
            if i999 > n - 1:
                i999 = n - 1
            out.append('%s{quantile="0.5"} %s' % (name, _g(float(vals[i50]))))
            out.append('%s{quantile="0.95"} %s' % (name, _g(float(vals[i95]))))
            out.append('%s{quantile="0.999"} %s' % (name, _g(float(vals[i999]))))
        out.append("%s_count %d" % (name, n))
        out.append("%s_sum %s" % (name, _g(float(sum(vals)))))
    return "\n".join(out)


def reset():
    """清空全部指标（进程内测试用）。"""
    REGISTRY["counters"].clear()
    REGISTRY["histos"].clear()
    del REGISTRY["order_c"][:]
    del REGISTRY["order_h"][:]
