"""cachex 现状演示。

第一段：建一个小缓存，写入与命中，看顺序与统计。
第二段：容量满时的淘汰，看最久未使用的那条先出。
第三段：预留的新口径演示位子（见文末注释）。
"""

from cachex import Cache


def main():
    print("=== 基础读写 ===")
    cache = Cache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    print("  命中 a:", cache.get("a"))
    print("  未命中 zzz:", cache.get("zzz"))
    print("  键序(旧到新):", cache.keys())
    print("  统计:", cache.stats())

    print("=== 满了淘汰 ===")
    cache.put("d", 4)  # 容量 3 已满，b 最久未使用先出
    print("  淘汰后键:", cache.keys())
    print("  b 还在吗:", "b" in cache)
    print("  统计:", cache.stats())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
