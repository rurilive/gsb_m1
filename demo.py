"""jobdag 演示：顺序跑一条补数链路，再用 Scheduler 跑并发、失败、超时重试与撤销。
"""

import threading
import time

from jobdag import JobGraph, Scheduler, SequentialRunner


def build_graph(log):
    """一条日志补数链路：扫描 -> 两路解析 -> 归并 -> 导出。"""

    def step(name, delay):
        def run():
            time.sleep(delay)
            log.append(name)
            return "%s done" % name
        return run

    graph = JobGraph()
    graph.add("scan", step("scan", 0.010))
    graph.add("parse_side", step("parse_side", 0.010), deps=["scan"])
    graph.add("parse_raw", step("parse_raw", 0.010), deps=["scan"])
    graph.add("merge", step("merge", 0.010), deps=["parse_raw", "parse_side"])
    graph.add("export", step("export", 0.005), deps=["merge"])
    return graph


def main():
    log = []
    graph = build_graph(log)
    print("执行序: %s" % " -> ".join(graph.topo_order()))

    start = time.perf_counter()
    report = SequentialRunner().run(graph)
    sequential_elapsed = time.perf_counter() - start
    for name in graph.names():
        print("  %-11s %-4s %6.1f ms  %s"
              % (name, report.status(name), report.durations[name] * 1000,
                 report.results.get(name)))
    print("全部成功: %s" % report.ok())
    print("按序调用: %s" % ", ".join(log))
    print("顺序总耗时: %.0f ms" % (sequential_elapsed * 1000))

    print()
    print("== 并发：同一张图 max_parallel=2 ==")
    log_parallel = []
    graph_parallel = build_graph(log_parallel)
    start = time.perf_counter()
    report_parallel = Scheduler(graph_parallel, 2).run()
    parallel_elapsed = time.perf_counter() - start
    print_report(graph_parallel, report_parallel)
    print("全部成功: %s" % report_parallel.ok())
    print("并发总耗时: %.0f ms（顺序 %.0f ms）"
          % (parallel_elapsed * 1000, sequential_elapsed * 1000))

    print()
    print("== 失败：parse_side 抛错，下游 skipped，另一路照跑 ==")
    failed_graph = JobGraph()
    failed_graph.add("scan", lambda: time.sleep(0.01) or "scanned")

    def broken():
        time.sleep(0.01)
        raise ValueError("脏分区，解析失败")

    failed_graph.add("parse_side", broken, deps=["scan"])
    failed_graph.add("parse_raw", lambda: time.sleep(0.01) or "raw",
                     deps=["scan"])
    failed_graph.add("merge", lambda: "merged",
                     deps=["parse_side", "parse_raw"])
    failed_graph.add("export", lambda: "exported", deps=["merge"])
    failed_graph.add("reconcile", lambda: "reconciled", deps=["parse_raw"])
    failed_report = Scheduler(failed_graph, 4).run()
    print_report(failed_graph, failed_report)

    print()
    print("== 超时与重试：单次超时 30ms，最多 3 次 ==")
    attempts = {"n": 0}

    def flaky_slow():
        attempts["n"] += 1
        if attempts["n"] < 3:
            time.sleep(0.08)
        return "third try ok"

    timeout_graph = JobGraph()
    timeout_graph.add("retry_job", flaky_slow, timeout=0.03, retries=2)
    timeout_graph.add("next", lambda: "next ok", deps=["retry_job"])
    timeout_report = Scheduler(timeout_graph, 2).run()
    print_report(timeout_graph, timeout_report)

    print()
    print("== 撤销：另一线程 cancel()，没开工的记 cancelled ==")
    cancel_graph = JobGraph()
    cancel_graph.add("scan", lambda: time.sleep(0.08) or "scanned")
    for name in ("parse_side", "parse_raw", "merge", "export"):
        deps = {"parse_side": ["scan"], "parse_raw": ["scan"],
                "merge": ["parse_side", "parse_raw"],
                "export": ["merge"]}[name]
        cancel_graph.add(name, lambda n=name: n + " done", deps=deps)
    scheduler = Scheduler(cancel_graph, 2)
    holder = {}
    runner_thread = threading.Thread(
        target=lambda: holder.setdefault("report", scheduler.run()))
    runner_thread.start()
    time.sleep(0.02)
    scheduler.cancel()
    runner_thread.join()
    print_report(cancel_graph, holder["report"])


def print_report(graph, report):
    for name in graph.names():
        state = report.status(name)
        tries = report.attempts.get(name, 0)
        suffix = " 尝试%d次" % tries if tries > 1 else ""
        detail = report.results.get(name)
        if detail is None and name in report.errors:
            detail = "%s: %s" % (
                type(report.errors[name]).__name__, report.errors[name])
        print("  %-11s %-9s %6.1f ms%s  %s"
              % (name, state, report.durations.get(name, 0.0) * 1000,
                 suffix, detail))


if __name__ == "__main__":
    main()
