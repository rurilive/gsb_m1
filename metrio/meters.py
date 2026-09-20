"""metrio.meters：进程内计数器/直方图收集与文本导出的对外薄壳。

模块函数是历史对外 API，全部转发到模块持有的默认 Registry 实例；
三种导出走"Registry.snapshot() -> render.*"管线，输出字节级稳定，
下游按字段顺序解析，别动输出。
"""

from __future__ import annotations

from metrio import render
from metrio.registry import Registry

_registry = Registry()


def inc(name: str, n: int = 1) -> int:
    """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""
    return _registry.inc(name, n)


def counter_value(name: str, default: int = 0) -> int:
    """读计数器当前值，没注册过返回 default。"""
    return _registry.counter_value(name, default)


def histogram(name: str) -> None:
    """注册一个空直方图（后面 observe 往里灌样本）。"""
    _registry.histogram(name)


def observe(name: str, value: float) -> None:
    """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""
    _registry.observe(name, value)


def render_text() -> str:
    """人看的文本导出。空注册表返回空串。"""
    return render.render_text(_registry.snapshot())


def export_json() -> str:
    """JSON 导出。字段顺序：name,count,sum,avg,min,max,p50,p95,p999（下游依赖）。"""
    return render.export_json(_registry.snapshot())


def export_prom() -> str:
    """prom 风格导出。字段顺序：quantile 行在前，_count/_sum 在后（下游依赖）。"""
    return render.export_prom(_registry.snapshot())


def reset() -> None:
    """清空全部指标（进程内测试用）。"""
    _registry.reset()
