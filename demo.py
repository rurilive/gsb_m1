"""replog 现状演示。

第一段：追加几条条目再按序号读回。
第二段：预留的主从复制与提交点推进演示位子（见文末注释）。
"""

from replog import InvalidIndex, LocalLog


def main():
    print("=== 基线：追加与读回 ===")
    log = LocalLog()
    log.append(term=1, command="set a=1")
    log.append(term=1, command="set b=2")
    log.append(term=2, command="del a")
    print("  日志长度:", log.size())
    print("  最后序号:", log.last_index())
    print("  最后任期:", log.last_term())
    print("  序号 2 的任期:", log.term_at(2))
    print("  序号 3 的命令:", log.get(3).command)

    print("=== 基线：截断与校验 ===")
    dropped = log.truncate_from(3)
    print("  丢掉条数:", len(dropped))
    print("  截断后长度:", log.size())
    print("  截断后最后任期:", log.last_term())
    try:
        log.get(5)
    except InvalidIndex as exc:
        print("  越界序号被拒:", exc)
    log.reset()
    print("  重置后长度:", log.size())

    # TODO(主从复制改造): 副本、主从复制、日志匹配与冲突截断、多数提交与提交点
    # 推进、任期与选举、崩溃恢复都补齐后，在这里加一段演示：
    # 建主从两个副本并用注入的确定消息队列互推条目，追加几条命令后按序复制；
    # 打印从落后时补发缺失条目、冲突时截断后缀再接收后主从日志前缀一致；
    # 打印多数确认后提交点推进、未达多数时提交点不动；
    # 打印副本崩溃重启后依据持久化日志恢复且重复条目幂等追加。


if __name__ == "__main__":
    main()
