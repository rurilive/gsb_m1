"""snapstore 现状演示。

第一段：逐键写入几个键、覆盖与删除，看各自独立的值与键集合。
第二段：预留的跨键快照与并发写隔离演示位子（见文末注释）。
"""

from snapstore import KeyValueStore


def main():
    print("=== 逐键写入（现有能力） ===")
    store = KeyValueStore()
    store.put("acct:1", 100)
    store.put("acct:2", 200)
    store.put("acct:1", 150)
    print("  get acct:1 ->", store.get("acct:1"))
    print("  get acct:2 ->", store.get("acct:2"))
    print("  delete acct:2 ->", store.delete("acct:2"))
    print("  keys ->", store.keys())
    print("  get acct:2 ->", store.get("acct:2"))

    # TODO(一致性快照与写时复制): 跨键事务与快照能力实现后，在这里加一段演示：
    # 先用 begin/commit 提交一组跨键写入并开一个 snapshot；
    # 再在快照创建之后继续提交另一组写入，打印同一时刻快照读到的旧整组值、
    # 与直接读底层拿到的新值，看两者分道扬镳，确认读不到半提交状态。

    # TODO(并发无撕裂与回收): 写写冲突与快照回收实现后，在这里加一段演示：
    # 起若干线程同时 commit 与 snapshot，断言每个快照读到的整组值都对应
    # 某个合法提交点；再释放快照，确认释放后底层空间被回收、引用计数归零。


if __name__ == "__main__":
    main()