"""LeaseManager 现状演示。

第一段：选主、为节点申请多段租约、续期与回收。
第二段：预留的批量能力演示位子（见文末注释）。
"""

from batchlease.lease import LeaseManager


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


def main():
    clock = FakeClock()
    mgr = LeaseManager({"alpha": 3, "beta": 1, "gamma": 2}, clock=clock)
    print("=== 选主、发租约与回收 ===")
    print(f"  primary -> {mgr.primary()!r}")
    first = mgr.acquire("alpha", ttl=10.0)
    print(f"  acquire('alpha', ttl=10) -> {first}")
    clock.advance(4.0)
    second = mgr.acquire("alpha", ttl=10.0)
    print(f"  推进 4 秒后再 acquire -> {second}")
    print(f"  segments('alpha') -> {mgr.segments('alpha')}")
    print(f"  expires_at('alpha') -> {mgr.expires_at('alpha')}")
    clock.advance(1.0)
    print(f"  renew('alpha') -> {mgr.renew('alpha')}")
    print(f"  held('beta') -> {mgr.held('beta')}, release('beta') -> {mgr.release('beta')}")
    print(f"  release('alpha') -> {mgr.release('alpha')}, "
          f"expires_at('alpha') -> {mgr.expires_at('alpha')}")

    # TODO(批量改造): 批量申请、相邻租约合并、批量释放实现后，在这里加一段演示：
    # 一次给多个节点申请（其中一批会因为成员表变动整体作废）、把同一节点的相邻
    # 租约合并看段落变化，以及批量释放里部分节点失败时报告了哪些成功。


if __name__ == "__main__":
    main()
