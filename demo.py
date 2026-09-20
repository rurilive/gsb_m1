"""演示 sfcache 的缓存命中、回源加载与并发合并。"""
import threading
import time

from sfcache import Cache


def main():
    calls = []

    def loader(key):
        calls.append(key)
        time.sleep(0.2)  # 模拟一次耗时的后端回源
        return "%s-v%d" % (key, calls.count(key))

    cache = Cache(loader, ttl=60)

    print("=== 首次请求 user:1（回源加载） ===")
    print("  ->", cache.get("user:1"))

    print("\n=== 再取一次 user:1（命中缓存，不再回源） ===")
    print("  ->", cache.get("user:1"))
    print("  回源次数:", len(calls))

    print("\n=== 8 个线程同时请求热门 key（合并成一次回源） ===")
    results = [None] * 8

    def worker(i):
        results[i] = cache.get("hot")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("  各线程结果:", results)
    print("  回源次数:", len(calls))

    print("\n=== 让 user:1 失效后重新拉取 ===")
    cache.invalidate("user:1")
    print("  ->", cache.get("user:1"))
    print("  回源次数:", len(calls))
    print("演示结束")


if __name__ == "__main__":
    main()
