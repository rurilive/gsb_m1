"""swimsim 现状演示。

第一段：静态成员表、观察、整表广播与按时间合并。
第二段：预留的失败探测与收敛演示位子（见文末注释）。
"""

from swimsim import ManualClock, Node


def main():
    print("=== 静态成员表 ===")
    clock = ManualClock(start=0.0, step=1.0)
    n1 = Node(name="n1", members=["n1", "n2", "n3"], clock=clock)
    print("  节点:", n1.name)
    print("  成员表:", n1.known())
    print("  初始存活:", [n1.is_alive(m) for m in n1.known()])

    clock.advance(3)
    n1.observe("n2", alive=True)
    print("  时间推进到:", clock.now)
    print("  n2 记录:", n1.record("n2"))

    print("=== 整表广播与合并 ===")
    snapshot = n1.gossip("n3")
    print("  广播快照:", snapshot)
    n4 = Node(name="n4", members=["n1", "n2", "n4"], clock=ManualClock(start=0.0))
    n4.merge(snapshot)
    print("  n4 合并后成员:", n4.known())
    print("  n4 看到的 n2:", n4.record("n2"))

    # TODO(协议扩展): 心跳与失败探测、怀疑与死亡三态、版本化传播、反熵与故障恢复补齐后，
    # 在这里加一段演示：让时钟推进过心跳超时，观察某个不再应答的成员从存活转到怀疑、
    # 再转到死亡；几个节点各自带版本号互相交换成员状态，低版本不覆盖高版本；
    # 反复随机挑对端做几轮反熵，最后打印各节点的成员视图，确认全网收敛到一致；
    # 再让先前死掉的成员带一个更高的版本重新加入，演示它自动复位并重新传播出去。


if __name__ == "__main__":
    main()