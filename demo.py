"""waitgraph 现状演示：把生产上踩过的几段场景跑一遍。

带“期望”的行是修好之后该有的样子，跑在现在的代码上多半对不上。
"""

import time

from waitgraph import FullScan, ResourceRegistry

WAYNE, TRISH, NEO = 4101, 4102, 4103


def scenario_stale_alarm():
    print("=== 场景一：环都解开了，健康检查还咬着报警 ===")
    reg = ResourceRegistry()
    reg.acquire(WAYNE, "idx-a")
    reg.acquire(TRISH, "idx-b")
    reg.acquire(WAYNE, "idx-b")     # 排队
    reg.acquire(TRISH, "idx-a")     # 排队，凑成环
    print("  闭环时 health:", reg.health())
    reg.release(TRISH, "idx-b")     # 放给 WAYNE，环没了
    print("  解开后 health:", reg.health(), " 权威等待边:", reg.waits())
    print("  期望：deadlocked False，cycle 为空")


def scenario_revived_edge():
    print("=== 场景二：进程失联，pid 复用后旧等待边诈尸 ===")
    reg = ResourceRegistry()
    reg.acquire(TRISH, "job-q")
    reg.acquire(WAYNE, "cfg")
    reg.acquire(WAYNE, "job-q")     # WAYNE 等 TRISH
    reg.drop(TRISH)                 # TRISH 崩溃，WAYNE 的等待作废
    reg.acquire(TRISH, "cfg")       # 新进程复用 4102，等 WAYNE 手里的 cfg
    print("  检测器 health:", reg.health())
    oracle = FullScan(reg)
    print("  全量参考:", {"deadlocked": oracle.deadlocked(),
                        "cycle": oracle.cycle_members()})
    print("  检测器图里残留的边:", sorted(reg.detector.graph.waits()))
    print("  期望：两边一致，都不报环")


def scenario_chain_tail():
    print("=== 场景三：等在链子上的正常进程被塞进环成员 ===")
    reg = ResourceRegistry()
    reg.acquire(TRISH, "a")
    reg.acquire(NEO, "b")
    reg.acquire(WAYNE, "a")         # WAYNE 等 TRISH，只是链条上游
    reg.acquire(TRISH, "b")         # TRISH 等 NEO
    reg.acquire(NEO, "a")           # NEO 等 TRISH，环在 TRISH 和 NEO 之间
    print("  检测器 health:", reg.health())
    oracle = FullScan(reg)
    print("  全量参考:", {"deadlocked": oracle.deadlocked(),
                        "cycle": oracle.cycle_members()})
    print("  期望：成员只有环上的两个进程，不带 WAYNE")


def scenario_big_graph():
    print("=== 场景四：十万节点图上单次变动的检测开销 ===")
    nodes = 100000
    width = 5
    holds = {}
    waits = []
    for base in range(0, nodes, width):
        pids = [100000 + base + i for i in range(width)]
        for i in range(width - 1):
            res = "r-%d" % pids[i]
            holds[res] = pids[i + 1]
            waits.append((pids[i], res, pids[i + 1]))
    reg = ResourceRegistry()
    reg.load_state(holds, waits)
    head, tail = 100000, 100004
    print("  装载完成：节点 %d，检测器图上 %d 条边"
          % (reg.detector.stats()["nodes"], len(reg.detector.graph.waits())))
    detector = reg.detector
    rounds = 3
    total_ms = 0.0
    total_visits = 0
    for _ in range(rounds):
        reg.acquire(head, "x-extra")
        detector.reset_stats()
        started = time.perf_counter()
        reg.acquire(tail, "x-extra")            # 局部闭环
        before = reg.health()
        total_ms += (time.perf_counter() - started) * 1000
        total_visits += detector.stats()["visits"]
        detector.reset_stats()
        started = time.perf_counter()
        reg.release(head, "x-extra")            # 环解开
        before = reg.health()
        total_ms += (time.perf_counter() - started) * 1000
        total_visits += detector.stats()["visits"]
        reg.release(tail, "x-extra")
    print("  变动加健康检查平均：%.1f ms，访问计数平均 %d"
          % (total_ms / (rounds * 2), total_visits // (rounds * 2)))
    oracle = FullScan(reg)
    started = time.perf_counter()
    oracle.deadlocked()
    print("  参考实现全量跑一次：%.1f ms" % ((time.perf_counter() - started) * 1000))
    print("  环解开后 health:", before)
    print("  期望：单次变动只碰与变动相关的节点，耗时和访问计数都比全量低两个量级")


def main():
    scenario_stale_alarm()
    print()
    scenario_revived_edge()
    print()
    scenario_chain_tail()
    print()
    scenario_big_graph()


if __name__ == "__main__":
    main()
