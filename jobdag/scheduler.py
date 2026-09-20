"""并发调度器。

固定大小的工作线程池跑 JobGraph：依赖满足的节点按 topo_order() 的先后
领取任务，同时在跑的节点数严格不超过 max_parallel。节点失败或超时后，
它的下游标 skipped，与它无关的分支照常跑完；cancel() 可从任意线程调用，
没开工的节点记 cancelled，在跑的节点跑完照记。
"""

import heapq
import threading
import time

from .report import RunReport


class Scheduler(object):
    """多线程并发调度。

    max_parallel 是工作线程数，也是同时在跑的节点上限；设为 1 时，执行
    顺序与 SequentialRunner 完全一致。每个 Scheduler 实例跑一次 run()，
    cancel() 可在 run() 之前或期间由其它线程调用。
    """

    def __init__(self, graph, max_parallel):
        if not isinstance(max_parallel, int) or max_parallel < 1:
            raise ValueError("max_parallel must be a positive int, got %r"
                             % (max_parallel,))
        self.graph = graph
        self.max_parallel = max_parallel
        self._cancel_event = threading.Event()

    def cancel(self):
        """请求撤销本次调度。幂等，可在 run() 前后、由任意线程调用。"""
        self._cancel_event.set()

    def run(self):
        graph = self.graph
        order = graph.topo_order()
        report = RunReport()
        if not order:
            return report

        index = dict((name, pos) for pos, name in enumerate(order))
        dependents = graph._dependents

        lock = threading.Lock()
        cond = threading.Condition(lock)
        ready = []
        in_flight = set()
        shutdown = False
        cancelled = self._cancel_event.is_set()

        if cancelled:
            for name in order:
                report.states[name] = "cancelled"
                report.attempts[name] = 0
            return report

        def enqueue_locked(name):
            heapq.heappush(ready, (index[name], name))

        def settle_locked(name, state, value, error, elapsed, tries):
            """落一个终态，并级联处理它的下游：入队或标 skipped。"""
            report.states[name] = state
            report.durations[name] = elapsed
            report.attempts[name] = tries
            if state == "ok":
                report.results[name] = value
            else:
                report.errors[name] = error

            stack = list(dependents.get(name, ()))
            while stack:
                dep_name = stack.pop()
                if dep_name in report.states:
                    continue
                job = graph.job(dep_name)
                dep_states = [report.states.get(d) for d in job.deps]
                if any(s in ("failed", "skipped", "timeout")
                       for s in dep_states):
                    report.states[dep_name] = "skipped"
                    report.attempts[dep_name] = 0
                    stack.extend(dependents.get(dep_name, ()))
                elif all(s == "ok" for s in dep_states):
                    enqueue_locked(dep_name)

        def worker():
            while True:
                with cond:
                    while not ready and not shutdown:
                        cond.wait()
                    if not ready:
                        return
                    _, name = heapq.heappop(ready)
                    in_flight.add(name)

                job = graph.job(name)
                value, error, tries, elapsed = self._execute(job)
                state = "timeout" if isinstance(error, TimeoutError) else (
                    "failed" if error is not None else "ok")

                with cond:
                    in_flight.discard(name)
                    settle_locked(
                        name, state,
                        value, error, elapsed, tries)
                    if len(report.states) == len(order):
                        cond.notify_all()
                        return
                    cond.notify_all()

        workers = [threading.Thread(target=worker, name="jobdag-worker-%d" % i)
                   for i in range(self.max_parallel)]
        with cond:
            for name in order:
                if not graph.job(name).deps:
                    enqueue_locked(name)

            def do_cancel():
                while ready:
                    _, name = heapq.heappop(ready)
                    if name not in report.states and name not in in_flight:
                        report.states[name] = "cancelled"
                        report.attempts[name] = 0
                for node_name in order:
                    if (node_name not in report.states
                            and node_name not in in_flight):
                        report.states[node_name] = "cancelled"
                        report.attempts[node_name] = 0

            if self._cancel_event.is_set():
                do_cancel()
            else:
                watcher_started = threading.Event()

                def watch_cancel():
                    watcher_started.set()
                    self._cancel_event.wait()
                    with cond:
                        do_cancel()
                        cond.notify_all()

                watcher = threading.Thread(target=watch_cancel,
                                           name="jobdag-cancel-watch")
                watcher.daemon = True
                watcher.start()
                watcher_started.wait()

            for thread in workers:
                thread.daemon = True
                thread.start()

            while len(report.states) < len(order):
                cond.wait()
            shutdown = True
            cond.notify_all()

        for thread in workers:
            thread.join()
        return report

    def _execute(self, job):
        """跑一个节点，含超时与重试。返回 (value, error, attempts, 墙钟秒)。"""
        start = time.perf_counter()
        tries = 0
        error = None
        while True:
            tries += 1
            value = None
            error = None
            if job.timeout is None:
                try:
                    value = job.fn()
                except Exception as exc:
                    error = exc
            else:
                outcome = {}

                def runner():
                    try:
                        outcome["value"] = job.fn()
                    except Exception as exc:
                        outcome["error"] = exc

                thread = threading.Thread(target=runner,
                                          name="jobdag-run-%s" % job.name)
                thread.daemon = True
                thread.start()
                thread.join(job.timeout)
                if thread.is_alive():
                    error = TimeoutError(
                        "job %r timed out after %.3fs"
                        % (job.name, job.timeout))
                elif "error" in outcome:
                    error = outcome["error"]
                else:
                    value = outcome.get("value")
            if error is None or tries > job.retries:
                break
        elapsed = time.perf_counter() - start
        return value, error, tries, elapsed
