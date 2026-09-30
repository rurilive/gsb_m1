"""lrucache 现状演示。

第一段：建一个固定容量缓存，看最近最少使用淘汰。
第二段：预留的迭代演示位子（见文末注释）。
"""

from lrucache.cache import LruCache


def main():
    print("=== 固定容量最近最少使用（现有能力） ===")
    cache = LruCache(3)
    for key, value in [("a", 1), ("b", 2), ("c", 3)]:
        cache.put(key, value)
    print(f"  写入 abc 后内容   -> {cache.snapshot()}")
    cache.get("a")
    print(f"  读取 a 后内容     -> {cache.snapshot()}")
    cache.put("d", 4)
    print(f"  再写入 d 后内容   -> {cache.snapshot()}")
    print(f"  累计淘汰次数      -> {cache.evictions()}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
