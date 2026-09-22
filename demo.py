"""docbase 现状演示。

第一段：写入、覆盖与主键读取。
第二段：关键词精确匹配查询与统计。
第三段：按相关度排序的演示位子（见文末注释）。
"""

from docbase import DocLibrary


def main():
    lib = DocLibrary()

    print("=== 写入、覆盖与读取 ===")
    lib.add("kb-001", "支付超时排查：先看网关日志里的 timeout 记录")
    lib.add("kb-002", "export timeout when the payment gateway hangs")
    lib.add("kb-003", "支付回调丢失的排查步骤")
    print("  count ->", lib.count())
    print("  ids   ->", lib.ids())
    print("  get(kb-002) ->", lib.get("kb-002"))
    replaced = lib.add("kb-003", "支付回调丢了怎么办：先看网关重试记录")
    print("  再写 kb-003，新建与否 ->", replaced)
    print("  get(kb-003) ->", lib.get("kb-003"))

    print("=== 精确匹配查询 ===")
    print("  search(timeout)   ->", lib.search("timeout"))
    print("  search(支)        ->", lib.search("支"))
    print("  search(gateway)   ->", lib.search("gateway"))
    print("  stats ->", lib.stats())

    print("=== 相关度排序（待补） ===")
    # 演示位子：docbase/rank.py 就位后，这里换成按分数取前 k 篇，
    # 并演示增删文档之后名次与统计量的变化。

    print("=== 删除 ===")
    print("  remove(kb-002) ->", lib.remove("kb-002"))
    print("  ids ->", lib.ids())
    print("  stats ->", lib.stats())


if __name__ == "__main__":
    main()
