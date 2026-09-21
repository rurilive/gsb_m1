"""leasekeeper 现状演示：发放续期归还、确定性脚本对拍、记号闸门。

第一段：LeaseKeeper 的基本用法，假时钟拨进拨出看过期。
第二段：脚本对拍，真实现逐条跑，纯模型纸上跑，回执逐条比。
第三段：FenceGuard 挡旧记号。
文末留了改造后的演示位子。
"""

from leasekeeper import (
    FakeClock,
    FenceGuard,
    LeaseConflict,
    LeaseKeeper,
    StaleFence,
    as_tuple,
    drive,
    make_script,
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

    # TODO(租约台改造): 幂等重放、崩溃重启后续号、高水位回灌与巡检
    # 耗时演示做完后，补在这里。


if __name__ == "__main__":
    main()
