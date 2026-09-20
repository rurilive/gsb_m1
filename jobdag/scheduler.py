"""并行调度器。

Scheduler 把 JobGraph 压成执行序后交给线程池真并行推进：依赖就绪即
派发，同时在跑的节点数不超过 max_parallel。节点失败或超时，下游整支
标 skipped，无关分支照跑完；别的线程调 cancel() 能撤掉还没开工的
节点，在跑的跑完照记，撤完报告定死。

超时的节点按失败记账，但线程没法强杀，底层那次调用会在后台跑到自然
结束，迟到的结果直接丢弃；配了重试时，重试可能与它短暂重叠。
"""

import concurrent.futures
import heapq
import queue
import threading
import time

from .report import RunReport


def _invoke(seq, name, fn, sink):
    """包一层节点调用：把结果或异常连同实际耗时塞进完成队列。"""
    start = time.perf_counter()
    try:
        value = fn()
    except BaseException as exc:
        sink.put((seq, name, exc, True, time.perf_counter() - start))
    else:
        sink.put((seq, name, value, False, time.perf_counter() - start))


class Scheduler(object):
    """按依赖关系并行调度一张 JobGraph。

    max_parallel 是并发上限；设 1 时执行序与 SequentialRunner 一致。
    """

    def __init__(self, graph, max_parallel=4):
        if max_parallel < 1:
            raise ValueError("max_parallel must be >= 1, got %r"
                             % (max_parallel,))
        self._graph = graph
        self._max_parallel = max_parallel
        self._cancelled = threading.Event()

    def cancel(self):
        """从任意线程请求撤销：未开工的记 cancelled，在跑的跑完照记。"""
        self._cancelled.set()

    def run(self):
        """跑完整张图（或被撤完），返回记好终态的 RunReport。"""
        graph = self._graph
        order = graph.topo_order()
        report = RunReport()
        dependents = {name: [] for name in order}
        remaining = {}
        for name in order:
            deps = graph.job(name).deps
            remaining[name] = len(deps)
            for dep in deps:
                dependents[dep].append(name)
        rank = {name: index for index, name in enumerate(order)}
        ready = [(rank[name], name) for name in order if remaining[name] == 0]
        heapq.heapify(ready)

        done_queue = queue.Queue()
        running = {}  # seq -> (name, deadline, started)
        seq = 0
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_parallel)
        try:
            while ready or running:
                while (ready and len(running) < self._max_parallel
                       and not self._cancelled.is_set()):
                    _, name = heapq.heappop(ready)
                    job = graph.job(name)
                    seq += 1
                    report.attempts[name] = report.attempts.get(name, 0) + 1
                    started = time.monotonic()
                    deadline = None
                    if job.timeout is not None:
                        deadline = started + job.timeout
                    running[seq] = (name, deadline, started)
                    executor.submit(_invoke, seq, name, job.fn, done_queue)
                if not running:
                    break
                wait = None
                deadlines = [entry[1] for entry in running.values()
                             if entry[1] is not None]
                if deadlines:
                    wait = max(0.0, min(deadlines) - time.monotonic())
                try:
                    event = done_queue.get(timeout=wait)
                except queue.Empty:
                    event = None
                now = time.monotonic()
                if event is not None:
                    ev_seq, name, payload, is_error, duration = event
                    # 超时被摘掉的节点迟到结果直接丢弃。
                    if running.pop(ev_seq, None) is not None:
                        report.durations[name] = (
                            report.durations.get(name, 0.0) + duration)
                        if is_error:
                            self._fail(graph, report, dependents, ready,
                                       rank, name, payload)
                        else:
                            report.states[name] = "ok"
                            report.results[name] = payload
                            for dependent in dependents[name]:
                                remaining[dependent] -= 1
                                if remaining[dependent] == 0:
                                    heapq.heappush(
                                        ready, (rank[dependent], dependent))
                for ev_seq, (name, deadline, started) in list(running.items()):
                    if deadline is not None and now >= deadline:
                        del running[ev_seq]
                        report.durations[name] = (
                            report.durations.get(name, 0.0) + now - started)
                        self._fail(graph, report, dependents, ready, rank,
                                   name, TimeoutError(
                                       "job %r timed out" % name))
        finally:
            executor.shutdown(wait=True)
        for name in order:
            if name not in report.states:
                report.states[name] = "cancelled"
        return report

    def _fail(self, graph, report, dependents, ready, rank, name, exc):
        """一次尝试失败后的记账：还有重试额度就重新排队，否则定失败并跳下游。"""
        job = graph.job(name)
        if (report.attempts[name] <= job.retries
                and not self._cancelled.is_set()):
            heapq.heappush(ready, (rank[name], name))
            return
        report.states[name] = "failed"
        report.errors[name] = exc
        stack = [name]
        while stack:
            node = stack.pop()
            for dependent in dependents[node]:
                if dependent not in report.states:
                    report.states[dependent] = "skipped"
                    stack.append(dependent)
