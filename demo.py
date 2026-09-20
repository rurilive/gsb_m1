"""jobdag 演示：声明一张补数链路图，先顺序跑一遍，再演示并行调度。"""

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
    print("顺序执行总耗时: %.1f ms" % ((time.perf_counter() - start) * 1000))
    for name in graph.names():
        print("  %-11s %-4s %6.1f ms  %s"
              % (name, report.status(name), report.durations[name] * 1000,
                 report.results.get(name)))
    print("全部成功: %s" % report.ok())
    print("按序调用: %s" % ", ".join(log))

    print()
    print("== 1) max_parallel=2 并行跑同一张图 ==")
    log2 = []
    graph2 = build_graph(log2)
    start = time.perf_counter()
    report2 = Scheduler(graph2, max_parallel=2).run()
    print("并行执行总耗时: %.1f ms" % ((time.perf_counter() - start) * 1000))
    for name in graph2.names():
        print("  %-11s %-4s %6.1f ms  %s"
              % (name, report2.status(name), report2.durations[name] * 1000,
                 report2.results.get(name)))
    print("全部成功: %s" % report2.ok())

    print()
    print("== 2) parse_side 抛错：下游 skipped，无关分支照跑 ==")

    def boom():
        raise ValueError("parse_side 解析失败")

    graph3 = JobGraph()
    graph3.add("scan", lambda: "scan done")
    graph3.add("parse_side", boom, deps=["scan"], retries=1)
    graph3.add("parse_raw", lambda: "parse_raw done", deps=["scan"])
    graph3.add("merge", lambda: "merge done",
               deps=["parse_raw", "parse_side"])
    graph3.add("export", lambda: "export done", deps=["merge"])
    report3 = Scheduler(graph3, max_parallel=2).run()
    for name in graph3.names():
        print("  %-11s %-7s attempts=%d"
              % (name, report3.status(name),
                 report3.attempts.get(name, 0)))
    print("  错误: %r" % report3.errors.get("parse_side"))

    print()
    print("== 3) 另一个线程调 cancel()：没开工的记 cancelled ==")
    graph4 = JobGraph()
    graph4.add("slow", lambda: time.sleep(0.2) or "slow done")
    graph4.add("queued", lambda: "queued done", deps=["slow"])
    graph4.add("later", lambda: "later done", deps=["queued"])
    scheduler = Scheduler(graph4, max_parallel=2)
    outcome = []
    worker = threading.Thread(target=lambda: outcome.append(scheduler.run()))
    worker.start()
    time.sleep(0.05)
    scheduler.cancel()
    worker.join()
    report4 = outcome[0]
    for name in graph4.names():
        print("  %-11s %s" % (name, report4.status(name)))


if __name__ == "__main__":
    main()
