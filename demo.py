"""LRUCache 现状演示。

第一段：容量驱逐——3 个位子放 4 个 key，看谁被挤出去。
第二段：TTL 过期——注入假时钟，看过期条目的读取与清理。
"""

from cachebox.cache import LRUCache


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


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

    print("=== TTL 过期（注入假时钟） ===")
    clock = FakeClock(1000.0)
    c = LRUCache(4, clock=clock)
    c.set("token", "abc", ttl=300)   # 5 分钟有效期
    c.set("config", {"v": 1})        # 永不过期
    print(f"  t=1000 get('token') -> {c.get('token')!r}")
    clock.now = 1300.0               # 恰好到期
    print(f"  t=1300 get('token') -> {c.get('token')!r}  # 到期即未命中")
    c.set("tmp1", 1, ttl=10)
    c.set("tmp2", 2, ttl=10)
    clock.now = 1400.0
    print(f"  purge_expired() -> 清掉 {c.purge_expired()} 条")
    print(f"  get('config') -> {c.get('config')!r}  # 无 ttl 不受影响")
    s = c.stats()
    print(f"  stats: hits={s['hits']} misses={s['misses']} "
          f"evicted={s['evicted']} expired={s['expired']}")


if __name__ == "__main__":
    main()
