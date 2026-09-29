"""txbox 现状演示。

第一段：跑一个全局锁事务，读写若干键后提交，看看数据怎么落存储；
第二段：预留的快照隔离演示位子（快照读、多版本、写写冲突中止，见文末注释）。
"""

from txbox import LockedTxn


def main():
    print("=== 全局锁事务 ===")
    engine = LockedTxn({"balance": 100})
    engine.begin()
    engine.set("balance", 70)
    engine.set("log", "withdraw 30")
    print("  事务内读 balance -> %s" % (engine.get("balance"),))
    engine.commit()
    print("  提交后存储 -> %s" % (engine.committed,))

    # TODO(快照隔离改造): 把 txbox 从全局锁扩成快照隔离引擎之后，
    # 在这里补第二段演示：开两个并发事务各自取快照读同一键，
    # 一个先提交、一个后提交，打印先提交后另一个事务仍读到旧快照
    # （可重复读），再让两者写同一键，演示后提交者检出写写冲突并被
    # 中止，被中止事务的改动全部不生效。快照读、多版本与冲突判定的
    # 语义见 README 的目标一节与任务描述。


if __name__ == "__main__":
    main()
