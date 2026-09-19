"""LRUCache 现状演示。

第一段：容量驱逐——3 个位子放 4 个 key，看谁被挤出去。
第二段：预留的过期演示位子（见文末注释）。
"""

from cachebox.cache import LRUCache


def main():
    print("=== 容量驱逐（3 个位子） ===")
    c = LRUCache(3)
    for k, v in [("a", 1), ("b", 2), ("c", 3)]:
        c.set(k, v)
    c.get("a")            # a 变成最近使用
    c.set("d", 4)         # 挤掉 b
    for k in "abcd":
        print(f"  get({k!r}) -> {c.get(k)!r}")
    s = c.stats()
    print(f"  stats: hits={s['hits']} misses={s['misses']} evicted={s['evicted']}")

    # TODO(过期改造): TTL 实现后，在这里加一段过期演示：
    # 注入假时钟给部分 key 设 ttl，推进时钟后展示 get 返回未命中、
    # purge_expired() 的清理结果，以及 stats 里 expired 计数的变化。


if __name__ == "__main__":
    main()
