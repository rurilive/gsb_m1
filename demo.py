"""ttlidx 现状演示。

第一段：建一张小索引，写入几条、按键取回、删掉一条，看命中未命中计数与主键顺序；
第二段：预留的 TTL 惰性过期与主动 sweep 演示位子（见文末注释）。
"""

from ttlidx import DictIndex


def main():
    print("=== 字典索引：写入取回删除 ===")
    idx = DictIndex()
    idx.set("u1", {"name": "ann", "dept": "eng"})
    idx.set("u2", {"name": "bob", "dept": "sales"})
    idx.set("u3", {"name": "cid", "dept": "eng"})
    print("  主键 %s，条数 %d" % (idx.keys(), len(idx)))
    print("  取 u2 -> %s" % (idx.get("u2"),))
    print("  取 u9 -> %s" % (idx.get("u9"),))
    idx.delete("u2")
    s = idx.stats()
    print("  删 u2 后主键 %s" % (idx.keys(),))
    print("  stats: live=%d hits=%d misses=%d" % (s["live"], s["hits"], s["misses"]))

    # TODO(TTL 惰性过期与主动 sweep): 在 ttlidx 里补出注入时钟、每条带过期时刻、
    # get 惰性判定过期并返回未命中的带 TTL 索引之后，在这里加一段演示：用一个手动
    # 推进的假时钟写入几条带不同 ttl 的条目，把时钟推过其中一条的过期时刻，打印
    # 这条 get 返回未命中而其余仍在；再调用 sweep 主动批量清理过期项，打印清掉的
    # 条数与清理后仍存活的条数，确认惰性判定与主动清理两条路得到的存活结果一致。


if __name__ == "__main__":
    main()
