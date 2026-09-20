"""jobdag 现状演示：声明一张补数链路图，顺序跑完一遍。

后半段留了并发调度改造后的演示位子。
"""

import time

from jobdag import JobGraph, SequentialRunner


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

    report = SequentialRunner().run(graph)
    for name in graph.names():
        print("  %-11s %-4s %6.1f ms  %s"
              % (name, report.status(name), report.durations[name] * 1000,
                 report.results.get(name)))
    print("全部成功: %s" % report.ok())
    print("按序调用: %s" % ", ".join(log))

    # TODO(并发调度改造): Scheduler 落地后在这里补三段演示：
    # 1) max_parallel=2 跑同一张图，对比总耗时和逐节点状态
    # 2) 让 parse_side 抛错，展示下游 skipped、无关分支照跑
    # 3) 另一个线程调 cancel()，展示撤掉后没开工的节点记 cancelled


if __name__ == "__main__":
    main()
