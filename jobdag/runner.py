"""顺序执行器。

按 JobGraph.topo_order() 逐个调用节点函数，把状态、返回值与耗时记进
RunReport。任一节点抛异常就停下，异常原样抛给调用方，后续节点不再执行。
"""

import time

from .report import RunReport


class SequentialRunner(object):
    """单线程、严格按执行序推进的调度。"""

    def run(self, graph):
        report = RunReport()
        for name in graph.topo_order():
            job = graph.job(name)
            start = time.perf_counter()
            try:
                value = job.fn()
            except Exception as exc:
                report.states[name] = "failed"
                report.errors[name] = exc
                report.durations[name] = time.perf_counter() - start
                raise
            report.durations[name] = time.perf_counter() - start
            report.states[name] = "ok"
            report.results[name] = value
        return report
