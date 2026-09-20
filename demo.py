"""quorkit 现状演示：法定人数漂移下的选主现场。

全程用假时钟，跑起来不用等真实时间；四段各自复现一类毛病。
"""

from quorkit import MemberTable, Quorum


class DemoClock:
    """演示用假时钟，可以手动往前拨。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        print(f"  ..时钟前进 {seconds}s，现在是 {self.now}s")
        return self.now


def main():
    print("=== 1. 成员扩容后，多数派门槛没跟着变 ===")
    clock = DemoClock()
    cluster = MemberTable(["n1", "n2", "n3"])
    q = Quorum(cluster, clock=clock, timeout=10.0)
    print(f"  起步 {len(cluster)} 个成员，多数派门槛 = {q.majority()}")
    cluster.add("n4")
    cluster.add("n5")
    print(f"  扩容到 {len(cluster)} 个成员，门槛还停在 {q.majority()}（本应随之重算）")
    q.heartbeat("n1", 0.0, 1)
    q.heartbeat("n2", 0.0, 1)
    print(f"  只有 n1、n2 报活，活跃 {sorted(q.active())}")
    print(f"  elect() -> {q.elect()}（5 个成员里活 2 个，不该当选）")

    print("=== 2. 本机超时不一致，两个节点各自宣布当选 ===")
    clock2 = DemoClock()
    cluster2 = MemberTable(["n1", "n2", "n3"])
    node_a = Quorum(cluster2, clock=clock2, timeout=30.0,
                    config={"heartbeat_timeout": 5.0})
    node_b = Quorum(cluster2, clock=clock2, timeout=5.0,
                    config={"heartbeat_timeout": 5.0})
    cluster2.add("n4")
    cluster2.add("n5")
    for node, ts in [("n1", 0.0), ("n2", 0.0), ("n3", 8.0), ("n4", 8.0)]:
        node_a.heartbeat(node, ts, 1)
        node_b.heartbeat(node, ts, 1)
    clock2.advance(12.0)
    print(f"  node-a（本机超时 30s）认为活着的是 {sorted(node_a.active())}")
    print(f"  node-b（本机超时 5s）认为活着的是 {sorted(node_b.active())}")
    print(f"  node-a.elect() -> {node_a.elect()}，node-b.elect() -> {node_b.elect()}")
    print("  两边都当选了（集群谈好的是 5s，谁也没按它算）")

    print("=== 3. 旧任期的心跳还是被当成有效 ===")
    clock3 = DemoClock()
    cluster3 = MemberTable(["n1", "n2", "n3"])
    q3 = Quorum(cluster3, clock=clock3, timeout=10.0,
                config={"heartbeat_timeout": 10.0})
    q3.heartbeat("n1", 0.0, 0)
    q3.heartbeat("n2", 0.0, 0)
    for _ in range(5):
        q3.elect()
    print(f"  连任几轮后任期 = {q3.term()}")
    accepted = q3.heartbeat("n3", 0.0, 2)
    print(f"  一个停在旧任期 2 的节点补发心跳，被采纳了吗: {accepted}（本该拒绝）")
    print(f"  此刻活跃 {sorted(q3.active())}")

    print("=== 4. 摘除的成员还在计票 ===")
    clock4 = DemoClock()
    cluster4 = MemberTable(["n1", "n2", "n3", "n4", "n5"])
    q4 = Quorum(cluster4, clock=clock4, timeout=10.0,
                config={"heartbeat_timeout": 10.0})
    for node in ("n1", "n2", "n3"):
        q4.heartbeat(node, 0.0, 0)
    cluster4.remove("n3")
    print(f"  n3 被运维摘除，在册剩 {sorted(cluster4.nodes())}，门槛 {q4.majority()}")
    print(f"  活跃判定里却仍含着 n3: {sorted(q4.active())}")
    print(f"  elect() -> {q4.elect()}（实际只活 2 个，不该当选）")

    print("演示结束")


if __name__ == "__main__":
    main()
