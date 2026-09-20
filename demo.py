"""LeaseManager 现状演示。

第一段：选主、为节点申请多段租约、续期与回收。
第二段：批量申请（含成员表变动整批作废）、段落合并与批量释放。
"""

from batchlease.lease import BatchAborted, LeaseManager


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

    print()
    print("=== 批量申请、段落合并与批量释放 ===")
    clock.advance(10.0)
    granted = mgr.batch_acquire(["beta", "gamma"], ttl=10.0)
    print(f"  batch_acquire(beta, gamma, ttl=10) -> {granted}")
    try:
        mgr.batch_acquire(
            ["beta", "gamma"],
            ttl=10.0,
            during=lambda nodes: mgr.table.add("latecomer", 0),
        )
    except BatchAborted as exc:
        print(f"  申请途中成员表被加人 -> {exc}")
    print(f"  作废后 beta 段落仍为 {mgr.segments('beta')}")
    clock.advance(2.0)
    mgr.acquire("beta", ttl=10.0)
    clock.advance(8.0)
    mgr.acquire("beta", ttl=5.0)
    print(f"  beta 合并前段落 -> {mgr.segments('beta')}")
    print(f"  compact('beta') -> {mgr.compact('beta')}")
    outcome = mgr.batch_release(["alpha", "beta", "ghost", "gamma"])
    print(f"  batch_release -> {outcome}")


if __name__ == "__main__":
    main()
