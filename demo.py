"""pagekit 现状演示。

第一段：请求页号与命中缺失，看计数与命中率。
第二段：容量满时的 LRU 淘汰，看最久未访问的页先出。
第三段：预留的写回与预取演示位子（见文末注释）。
"""

from pagekit import PageSimulator


def main():
    print("=== 基础读写 ===")
    sim = PageSimulator(capacity=3)
    for page in (1, 2, 1, 1, 3):
        sim.access(page)
    print("  常驻页:", sim.resident())
    print("  统计:", sim.stats())
    print("  命中率:", sim.hit_ratio())

    print("=== LRU 淘汰 ===")
    sim.access(2)  # 2 变最新
    sim.access(4)  # 容量 3 已满，1 最久未用先出
    print("  常驻页:", sim.resident())
    print("  1 还在吗:", 1 in sim)
    print("  统计:", sim.stats())

    # TODO(写回与预取): LRU-K 的 K 次访问历史、脏页写回计数、写回缓冲合并
    # 与预取命中统计就位后在这里补两段演示：连续访问两次的页才是热页，
    # 淘汰脏页要让写回次数加一，命中写回缓冲要把重复写合并成一次，
    # 并报出命中、缺失、淘汰、写回、合并与预取命中六个指标。


if __name__ == "__main__":
    main()