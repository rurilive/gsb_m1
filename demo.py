"""bitag 现状演示。

第一段：写入记录，看倒排表、记录读取、覆盖写与占用口径。
第二段：布尔查询走 SetEngine，含补集与差集。
第三段：预留的位图索引演示位子（见文末注释）。
"""

from bitag import SetEngine, TagStore, deep_size, evaluate, human, parse


def main():
    store = TagStore()
    print("=== 写入记录 ===")
    records = [
        (1001, [3, 7]),
        (1002, [7, 9]),
        (1003, [3, 9]),
        (1004, [11]),
        (1005, []),
    ]
    for rid, labels in records:
        store.add(rid, labels)
    print("  ids         ->", store.ids())
    print("  labels      ->", store.labels())
    print("  get(1001)   ->", store.get(1001))
    print("  postings 7  ->", sorted(store.postings(7)))
    print("  stats       ->", store.stats())
    print("  整库占用    ->", human(deep_size(store)))

    print("=== 覆盖写 ===")
    store.add(1002, [9])
    print("  1002 新标签 ->", store.get(1002))
    print("  postings 7  ->", sorted(store.postings(7)))

    print("=== 布尔查询（SetEngine） ===")
    engine = SetEngine(store)
    for text in ("3", "3&7", "3|9", "~7", "7-3", "3&(7|~9)"):
        print("  %-10s -> %s" % (text, evaluate(parse(text), engine)))
    print("  engine.stats ->", engine.stats())
    print("  倒排表占用   ->", human(deep_size(store)))

    print("=== 位图索引演示（待补） ===")
    # 演示位子：建 BitmapIndex，跟 SetEngine 对拍同一批查询，
    # 打印两边耗时、索引占用与桶级统计。


if __name__ == "__main__":
    main()
