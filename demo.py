"""docbase 演示。

第一段：写入、覆盖与主键读取。
第二段：关键词精确匹配查询与统计。
第三段：BM25 相关度排序。
第四段：删除文档，名次随之变化。
"""

from docbase import BM25Index, DocLibrary


def show_ranked(index, query, k):
    print("  ranked(%r, k=%d)" % (query, k))
    for doc_id, score in index.search(query, k):
        print("    %-8s %.4f" % (doc_id, score))


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

    print("=== 相关度排序 ===")
    index = BM25Index(lib)
    show_ranked(index, "支付 超时", 3)
    show_ranked(index, "gateway timeout", 3)
    print("  index stats ->", index.stats())

    print("=== 删除 ===")
    print("  remove(kb-002) ->", lib.remove("kb-002"))
    print("  ids ->", lib.ids())
    print("  stats ->", lib.stats())

    print("=== 删除后的相关度排序 ===")
    show_ranked(index, "gateway timeout", 3)
    print("  index stats ->", index.stats())


if __name__ == "__main__":
    main()
