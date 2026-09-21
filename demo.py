"""leasekeeper 现状演示：发放续期归还、确定性脚本对拍、记号闸门。

第一段：LeaseKeeper 的基本用法，假时钟拨进拨出看过期。
第二段：脚本对拍，真实现逐条跑，纯模型纸上跑，回执逐条比。
第三段：FenceGuard 挡旧记号。
第四段：幂等重发、崩溃续号、高水位回灌、时钟回拨与崩溃对拍。
"""

from leasekeeper import (
    DurableLeaseKeeper,
    FakeClock,
    FenceGuard,
    LeaseConflict,
    LeaseKeeper,
    MemoryJournal,
    StaleFence,
    as_tuple,
    drive,
    drive_durable,
    make_durable_script,
    make_script,
    model_durable,
    model_run,
)


def main():
    print("=== 发放、续期、过期与归还 ===")
    clock = FakeClock(start=1000.0)
    keeper = LeaseKeeper(clock=clock.current)
    lease = keeper.grant("db.primary", "n1", 30.0)
    print("  发出:", lease.lease_id, "记号:", lease.token, "到期:", lease.expires_at)
    try:
        keeper.grant("db.primary", "n2", 30.0)
    except LeaseConflict as exc:
        print("  撞车被拒:", exc)
    renewed = keeper.renew(lease.lease_id, "n1")
    print("  n1 续期, 到期挪到:", renewed.expires_at)
    clock.advance(31.0)
    print("  过期之后再读:", keeper.get("db.primary"))
    second = keeper.grant("db.primary", "n2", 30.0)
    print("  过期后重发:", second.lease_id, "记号:", second.token)
    print("  stats:", keeper.stats())

    print("=== 脚本对拍：真实现逐条跑，纯模型纸上跑 ===")
    script = make_script(seed=7, resources=("db.primary", "cache.hot"), steps=120)
    fresh_clock = FakeClock()
    got = drive(LeaseKeeper(clock=fresh_clock.current), script, fresh_clock)
    want_receipts, final = model_run(script)
    same = [as_tuple(r) for r in got] == [as_tuple(r) for r in want_receipts]
    print("  事件:", len(script), "条, 回执逐条一致:", same)
    print("  终局持有:", final["holders"], " 总发放:", final["grants"])

    print("=== 记号闸门 ===")
    guard = FenceGuard()
    guard.check("db.primary", second.token)
    print("  记号", second.token, "放行, 高水位:", guard.high_water("db.primary"))
    try:
        guard.check("db.primary", lease.token)
    except StaleFence as exc:
        print("  旧记号", lease.token, "被挡下:", exc)

    print("=== 幂等重放：同一请求标识的并发重试只发一份 ===")
    journal = MemoryJournal()
    boot_clock = FakeClock(start=5000.0)
    dk = DurableLeaseKeeper(clock=boot_clock.current, journal=journal)
    replies = [
        dk.grant("vol.leader", "n9", 30.0, request_id="post-777")
        for _ in range(3)
    ]
    print("  连领三次同号:", {l.token for l in replies}, "份:", replies[0].lease_id)
    try:
        dk.grant("vol.leader", "n2", 30.0, request_id="post-778")
    except LeaseConflict:
        print("  别的请求在租期内撞车被拒")
    print("  撞车请求重试仍是撞车:", end=" ")
    try:
        dk.grant("vol.leader", "n2", 30.0, request_id="post-778")
    except LeaseConflict:
        print("LeaseConflict")

    print("=== 崩溃重启：记号只增，历史高水位灌回闸门 ===")
    before = dk.stats().last_token
    reborn = DurableLeaseKeeper.recover(
        journal, clock=boot_clock.current
    )
    print("  崩前记号:", before, " 恢复后接着发:",
          reborn.grant("vol.follower", "n3", 30.0,
                       request_id="post-800").token)
    boot_clock.advance(31.0)
    reborn.grant("vol.leader", "n2", 30.0, request_id="post-801")
    print("  vol.leader 历史高水位:", reborn.high_water("vol.leader"))
    guard = reborn.seal_guard(FenceGuard())
    try:
        guard.check("vol.leader", replies[0].token)
    except StaleFence:
        print("  旧纪元旧号", replies[0].token, "被闸门挡下")

    print("=== 时钟回拨 + 崩溃对拍 ===")
    rollback_clock = FakeClock(start=9000.0)
    rk = DurableLeaseKeeper(clock=rollback_clock.current,
                            journal=MemoryJournal())
    old = rk.grant("disk.a", "n1", 10.0, request_id="a1")
    rollback_clock.advance(11.0)
    print("  到期即回收:", rk.get("disk.a") is None)
    rollback_clock.set(rollback_clock.current() - 7.0)
    print("  钟被拨回 7 秒, 旧租约不复活:", rk.get("disk.a") is None)
    print("  旧号续期也被拒:", rk.renew(old.lease_id, "n1") is None)
    dscript = make_durable_script(seed=13, steps=160)
    dclock = FakeClock()
    djournal = MemoryJournal()

    def make_boot(existing):
        if existing is None:
            return DurableLeaseKeeper(clock=dclock.current, journal=djournal)
        return DurableLeaseKeeper.recover(existing, clock=dclock.current)

    got_d = drive_durable(make_boot, dscript, dclock)
    want_d, final_d = model_durable(dscript)
    print("  含崩溃/并发的脚本回执逐条一致:", got_d == want_d)
    print("  终局最后记号:", final_d["last_token"],
          " 高水位条数:", len(final_d["high_water"]))


if __name__ == "__main__":
    main()
