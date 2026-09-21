"""leasekeeper 现状演示：发放续期归还、确定性脚本对拍、记号闸门。

第一段：LeaseKeeper 的基本用法，假时钟拨进拨出看过期。
第二段：脚本对拍，真实现逐条跑，纯模型纸上跑，回执逐条比。
第三段：FenceGuard 挡旧记号。
文末留了改造后的演示位子。
"""

from leasekeeper import (
    DurableKeeper,
    FakeClock,
    FenceGuard,
    LeaseConflict,
    LeaseKeeper,
    MonotonicClamp,
    StaleFence,
    as_dtuple,
    as_tuple,
    drive,
    drive_durable,
    make_dscript,
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

    print("=== 单调钟钳制：回拨不多活 ===")
    wall = FakeClock(start=1000.0)
    steady = MonotonicClamp(wall.current)
    clamped = DurableKeeper(clock=steady.current)
    ticking = clamped.grant("db.primary", "n1", 10.0)
    wall.advance(6.0)
    clamped.renew(ticking.lease_id, "n1", 10.0)
    wall.set(999.0)
    print("  NTP 回拨 7 秒, 钟面:", wall.current(),
          " 租约台看到:", steady.current())
    wall.set(1016.0)
    print("  到点准时过期:", clamped.get("db.primary") is None,
          "(没多活 7 秒)")

    print("=== 幂等发放：同一请求重试拿回同一份 ===")
    import os
    import tempfile

    journal = os.path.join(
        tempfile.mkdtemp(prefix="leasekeeper-demo-"), "lease.journal"
    )
    durable_clock = FakeClock(start=2000.0)
    guard2 = FenceGuard()

    def boot():
        return DurableKeeper(
            clock=durable_clock.current, journal=journal, fence=guard2
        )

    keeper = boot()
    first = keeper.grant("cache.hot", "n1", 30.0, request_id="req-1")
    again = keeper.grant("cache.hot", "n1", 30.0, request_id="req-1")
    print("  首发记号:", first.token, " 重试记号:", again.token,
          " 同一份:", first == again, " 发放数:", keeper.stats().grants)

    print("=== 崩溃重启：续号、回收、高水位回灌 ===")
    keeper = boot()
    print("  重启后续发:", keeper.stats().last_token + 1,
          " 崩溃前未归还的已回收:", keeper.get("cache.hot") is None)
    renewed_grant = keeper.grant("cache.hot", "n2", 30.0)
    print("  新租约记号:", renewed_grant.token,
          " 闸门高水位:", guard2.high_water("cache.hot"))
    try:
        guard2.check("cache.hot", first.token)
    except StaleFence as exc:
        print("  旧持有者记号", first.token, "被挡下:", exc)

    print("=== 带崩溃与并发重试的脚本对拍 ===")
    script = make_dscript(
        seed=7, resources=("db.primary", "cache.hot"), steps=200
    )
    script_clock = FakeClock()
    script_guard = FenceGuard()
    script_journal = os.path.join(
        tempfile.mkdtemp(prefix="leasekeeper-demo-"), "script.journal"
    )

    def script_boot():
        return DurableKeeper(
            clock=script_clock.current,
            journal=script_journal,
            fence=script_guard,
        )

    got, last_keeper = drive_durable(script_boot, script, script_clock)
    want_receipts, final = model_durable(script)
    same = [as_dtuple(r) for r in got] == [as_dtuple(r) for r in want_receipts]
    crashes = sum(1 for event in script if event[0] == "crash")
    print("  事件:", len(script), "条 (含崩溃", crashes, "次),",
          "回执逐条一致:", same)
    print("  终局持有:", final["holders"],
          " 最后记号:", last_keeper.stats().last_token,
          "对上:", last_keeper.stats().last_token == final["last_token"])
    water_ok = all(
        script_guard.high_water(resource) == token
        for resource, token in final["water"].items()
    )
    print("  闸门高水位逐资源对上:", water_ok)


if __name__ == "__main__":
    main()
