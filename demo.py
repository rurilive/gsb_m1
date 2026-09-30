"""pdsu 现状演示。

第一段：朴素可持久化并查集——建一个六元素森林，连做几次合并，回查旧版本
的连通性、集合大小与分组，打印结果。
第二段：预留的路径仅改动与独立做法对照演示位子（见文末注释）。
"""

from pdsu import PersistentDSU


def main():
    print("=== 整份拷贝的朴素可持久化并查集（基线） ===")
    d = PersistentDSU(6, list("abcdef"))
    v1 = d.union(0, "a", "b")
    v2 = d.union(v1, "c", "d")
    v3 = d.union(v2, "b", "c")
    v4 = d.union(v3, "e", "f")
    print("  版本总数 %d，累计合并次数 %d" % (d.version_count(), d.merge_count()))
    for v in range(d.version_count()):
        print("  版本 %d 分组 %r" % (v, d.groups(v)))
    print("  版本 %d 里 a 与 d 是否连通 %s" % (v3, d.connected(v3, "a", "d")))
    print("  版本 %d 里 a 所在集合大小 %d" % (v4, d.size(v4, "a")))
    print("  版本 %d 里 d 的代表元编号 %d" % (v4, d.representative(v4, "d")))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
