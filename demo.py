"""guardcache 现状演示：缓存被污染后长期返回错误结果的几类现象。

逐段演示四个现象，输出里的 loader 调用次数是关键：
  1. 回源异常后缓存里被写进坏值，之后一直命中
  2. 同 key 并发未命中，多个 loader 同时跑，旧值覆盖新值
  3. 热 key 命中时被续期，TTL 形同虚设，一直不换新
  4. 负条目和正常条目共用一个容量池，被挤掉后不存在的 key 又打下游
"""

import threading

from guardcache import GuardCache, NotFound


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def demo_poisoned_on_error():
    print("=== 1. 回源异常后缓存被污染 ===")
    calls = []

    def loader(key):
        calls.append(key)
        raise RuntimeError("backend timeout")

    cache = GuardCache(loader, ttl=60, capacity=8)
    try:
        cache.get("pay:1")
    except RuntimeError as exc:
        print("  第一次 get ->", exc)
    value = cache.get("pay:1")
    print("  第二次 get ->", value, "（缓存里留下了坏值，没再回源）")
    print("  loader 调用次数:", len(calls))


def demo_concurrent_overwrite():
    print("\n=== 2. 并发未命中：旧快照覆盖新快照 ===")
    calls = []
    guard = threading.Lock()
    gate = threading.Event()
    first_in = threading.Event()

    def loader(key):
        with guard:
            calls.append(key)
            n = len(calls)
        if n == 1:             # 慢的那个先到，回源却很慢
            first_in.set()
            gate.wait(5.0)
            return "旧快照"
        return "新快照"         # 快的那个后到，带回新数据

    cache = GuardCache(loader, ttl=60, capacity=8)
    result = {}

    def worker(name):
        result[name] = cache.get("hot:cfg")

    slow = threading.Thread(target=worker, args=("slow",))
    slow.start()
    first_in.wait(5.0)
    fast = threading.Thread(target=worker, args=("fast",))
    fast.start()
    fast.join(5.0)
    gate.set()
    slow.join(5.0)

    print("  两次 get 各自拿到:", result.get("slow"), "/", result.get("fast"))
    print("  回源次数:", len(calls))
    print("  缓存里最终留下的值:", cache.get("hot:cfg"), "（旧值把新值盖掉了）")


def demo_ttl_never_expires():
    print("\n=== 3. 热 key 命中即续期，永不更新 ===")
    clock = FakeClock()
    calls = []

    def loader(key):
        calls.append(key)
        return "配置v%d" % len(calls)

    cache = GuardCache(loader, ttl=5, capacity=8, clock=clock)
    cache.get("flag")
    for _ in range(20):
        clock.advance(1)
        cache.get("flag")
    print("  ttl=5 秒、时钟推了 20 秒，get 仍返回:", cache.get("flag"))
    print("  loader 调用次数:", len(calls))


def demo_negative_evicted():
    print("\n=== 4. 负条目被容量挤掉，不存在的 key 反复回源 ===")
    clock = FakeClock()
    calls = []

    def loader(key):
        calls.append(key)
        if key.startswith("ghost"):
            raise NotFound(key)
        return "值:" + key

    cache = GuardCache(loader, ttl=60, capacity=2, negative_ttl=60, clock=clock)

    def ghost_loads():
        return calls.count("ghost")

    for _ in range(2):
        try:
            cache.get("ghost")
        except NotFound:
            pass
    print("  连问两次 ghost，ghost 回源次数:", ghost_loads())
    cache.get("k1")
    cache.get("k2")
    try:
        cache.get("ghost")
    except NotFound:
        pass
    print("  容量被 k1/k2 占满后再问 ghost，ghost 回源次数:", ghost_loads())


def main():
    demo_poisoned_on_error()
    demo_concurrent_overwrite()
    demo_ttl_never_expires()
    demo_negative_evicted()
    print("\n演示结束")


if __name__ == "__main__":
    main()
