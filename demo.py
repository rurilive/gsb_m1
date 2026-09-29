"""expirex 现状演示。

第一段：超出容量后写入，看最朴素的删除行为。
第二段：预留的 TTL 与 LRU 改造演示位子（见文末注释）。
"""

from expirex import LimitedDict


def main():
    print("=== 带上限的字典 ===")
    store = LimitedDict(capacity=3)
    store.set("a", 1)
    store.set("b", 2)
    store.set("c", 3)
    print("  写入三个键:", store.keys())

    store.set("d", 4)  # 容量 3 已满，随意删掉一个键
    print("  再加一个 d 后:", store.keys())
    print("  a 还在吗:", "a" in store)
    print("  命中 d:", store.get("d"))

    # TODO(淘汰与过期改造): 注入时钟与 TTL 就位后在这里补一轮演示：
    # 容量满时先淘汰已过期项、再按 LRU 淘汰未过期项，
    # 并报出命中、未命中、淘汰、过期各指标。


if __name__ == "__main__":
    main()
