"""LeaseManager 现状演示。

第一段：选主、为节点申请多段租约、续期与回收。
第二段：批量申请（成员表变动整批作废）、相邻段落合并、批量释放部分成功。
"""

from batchlease.lease import LeaseManager, MembershipChanged


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start
        self._on_read = None

    def __call__(self):
        if self._on_read is not None:
            hook, self._on_read = self._on_read, None
            hook()
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now

    def once(self, hook):
        """注册下一次读钟时触发一次的回调。"""
        self._on_read = hook


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
    print("=== 批量申请、合并与批量释放 ===")
    clock2 = FakeClock()
    mgr2 = LeaseManager({"alpha": 3, "beta": 1, "gamma": 2}, clock=clock2)
    granted = mgr2.acquire_batch(["alpha", "beta", "gamma"], ttl=10.0)
    print(f"  acquire_batch(alpha/beta/gamma, ttl=10) -> {granted}")

    clock2.advance(4.0)
    mgr2.acquire("alpha", ttl=10.0)
    print(f"  推进 4 秒后 alpha 再申请一段 -> {mgr2.segments('alpha')}")
    print(f"  merge('alpha') -> {mgr2.merge('alpha')}")

    print("  申请途中成员表加入 late 节点：")
    clock2.once(lambda: mgr2.table.add("late", 0))
    try:
        mgr2.acquire_batch(["alpha", "beta"], ttl=5.0)
    except MembershipChanged as exc:
        print(f"    -> {type(exc).__name__}: {exc}")
    print(f"    整批作废，beta 段落仍为 -> {mgr2.segments('beta')}")

    result = mgr2.release_batch(["alpha", "gamma", "idle", "ghost"])
    print(f"  release_batch(alpha/gamma/idle/ghost) -> {result}")
    print(f"    beta 不受影响 -> segments {mgr2.segments('beta')}, "
          f"held {mgr2.held('beta')}")


if __name__ == "__main__":
    main()
