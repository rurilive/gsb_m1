"""确定性事件脚本：生成、驱动、纯模型对拍三件套。

脚本是 (事件名, ...) 元组串：grant、renew、release 对某资源某持有者
下手，sleep 把假时钟往前拨。make_script 按 seed 生成，同 seed 一字不
差；drive 把脚本喂给真实现逐条跑，记下每条回执；model_run 不碰任何真
对象，在纸上把同一份脚本再跑一遍，算出逐条回执与终局。两边用 as_tuple
抹平类型后逐条对得上，实现才算没跑偏。
"""

import random
import threading

from leasekeeper.keeper import Lease, LeaseConflict


def make_script(seed, resources=("db.primary",), steps=120,
                holders=("n1", "n2", "n3")):
    """按 seed 生成 steps 条事件：掺发放、续期、归还与拨钟。"""
    rng = random.Random(seed)
    script = []
    for _ in range(steps):
        roll = rng.random()
        resource = rng.choice(resources)
        holder = rng.choice(holders)
        if roll < 0.38:
            script.append(
                ("grant", resource, holder, float(rng.choice((2.0, 5.0, 9.0))))
            )
        elif roll < 0.72:
            script.append(("renew", resource, holder, rng.choice((None, 4.0))))
        elif roll < 0.86:
            script.append(("release", resource, holder))
        else:
            script.append(("sleep", float(rng.choice((0.5, 1.0, 3.0, 7.0)))))
    return script


def drive(keeper, script, clock):
    """把脚本逐条喂给真实现，返回与脚本等长的回执列表。

    grant 撞上活租约回执记 None；renew 落在空资源、非持有者或已过期
    上记 None；release 只有当前持有者在租约还活着时才 True；sleep 回
    执是拨完后的时刻。
    """
    receipts = []
    for event in script:
        kind = event[0]
        if kind == "grant":
            _, resource, holder, ttl = event
            try:
                receipts.append(keeper.grant(resource, holder, ttl))
            except LeaseConflict:
                receipts.append(None)
        elif kind == "renew":
            _, resource, holder, ttl = event
            lease_id = _current(keeper, resource, holder)
            receipts.append(
                None if lease_id is None
                else keeper.renew(lease_id, holder, ttl)
            )
        elif kind == "release":
            _, resource, holder = event
            lease_id = _current(keeper, resource, holder)
            receipts.append(
                False if lease_id is None
                else keeper.release(lease_id, holder)
            )
        else:
            receipts.append(clock.advance(event[1]))
    return receipts


def model_run(script, start=0.0):
    """纯模型在纸上跑同一份脚本，返回 (逐条回执, 终局)。

    终局带 holders 每个资源当前的持有者（空是 None）与 grants 总发放
    次数。回执口径与 drive 完全一致，租约以字段元组出现。
    """
    now = start
    token = 0
    state = {}
    seen = []
    receipts = []
    for event in script:
        kind = event[0]
        if kind == "grant":
            _, resource, holder, ttl = event
            if resource not in state and resource not in seen:
                seen.append(resource)
            current = state.get(resource)
            if current is not None and now < current["expires_at"]:
                receipts.append(None)
                continue
            token += 1
            state[resource] = {
                "lease_id": "L%06d" % token,
                "resource": resource,
                "holder": holder,
                "token": token,
                "ttl": ttl,
                "expires_at": now + ttl,
            }
            receipts.append(_tuple_of(state[resource]))
        elif kind == "renew":
            _, resource, holder, ttl = event
            current = state.get(resource)
            if (current is None or current["holder"] != holder
                    or now >= current["expires_at"]):
                receipts.append(None)
                continue
            extend = current["ttl"] if ttl is None else ttl
            current["ttl"] = extend
            current["expires_at"] = now + extend
            receipts.append(_tuple_of(current))
        elif kind == "release":
            _, resource, holder = event
            current = state.get(resource)
            if (current is not None and current["holder"] == holder
                    and now < current["expires_at"]):
                del state[resource]
                receipts.append(True)
            else:
                receipts.append(False)
        else:
            now += event[1]
            receipts.append(now)
    final = {
        "holders": {
            resource: (
                state[resource]["holder"]
                if resource in state and now < state[resource]["expires_at"]
                else None
            )
            for resource in seen
        },
        "grants": token,
    }
    return receipts, final


def as_tuple(receipt):
    """把回执抹成可比较的形态：租约变字段元组，其余原样返回。"""
    if isinstance(receipt, Lease):
        return _tuple_of(
            {
                "lease_id": receipt.lease_id,
                "resource": receipt.resource,
                "holder": receipt.holder,
                "token": receipt.token,
                "ttl": receipt.ttl,
                "expires_at": receipt.expires_at,
            }
        )
    if isinstance(receipt, dict):
        return _tuple_of(receipt)
    return receipt


def _tuple_of(fields):
    return (
        fields["lease_id"],
        fields["resource"],
        fields["holder"],
        fields["token"],
        fields["ttl"],
        fields["expires_at"],
    )


def _current(keeper, resource, holder):
    lease = keeper.get(resource)
    if lease is None or lease.holder != holder:
        return None
    return lease.lease_id


# ---------------------------------------------------------------------------
# 崩溃恢复对拍：在旧四事件之外加 grantq（带请求标识的幂等发放）、
# parallel（同标识并发重试）、crash（从日志重放重建租约台）。
# ---------------------------------------------------------------------------


def make_durable_script(seed, resources=("db.primary", "cache.hot"),
                        steps=240, holders=("n1", "n2", "n3")):
    """生成带幂等发放、并发重试与崩溃重启的确定性事件串。

    新增事件：
    - ("grantq", resource, holder, ttl, request_id)
    - ("parallel", resource, holder, ttl, request_id, 路数)
    - ("crash",)
    request_id 有概率复用本资源上一次成功发放的标识，制造重试现场。
    """
    rng = random.Random(seed)
    script = []
    last_request = {}
    for _ in range(steps):
        roll = rng.random()
        resource = rng.choice(resources)
        holder = rng.choice(holders)
        if roll < 0.04:
            script.append(("crash",))
        elif roll < 0.40:
            ttl = float(rng.choice((2.0, 5.0, 9.0, 20.0)))
            if rng.random() < 0.35 and resource in last_request:
                request_id, holder, ttl = last_request[resource]
            else:
                request_id = "req-%d" % len(script)
                last_request[resource] = (request_id, holder, ttl)
            script.append(("grantq", resource, holder, ttl, request_id))
        elif roll < 0.52:
            if resource in last_request and rng.random() < 0.8:
                request_id, holder, ttl = last_request[resource]
            else:
                request_id = "req-par-%d" % len(script)
                ttl = float(rng.choice((2.0, 5.0, 20.0)))
                last_request[resource] = (request_id, holder, ttl)
            ways = rng.choice((2, 3, 4))
            script.append(("parallel", resource, holder, ttl,
                           request_id, ways))
        elif roll < 0.74:
            script.append(("renew", resource, holder, rng.choice((None, 4.0))))
        elif roll < 0.86:
            script.append(("release", resource, holder))
        else:
            script.append(("sleep", float(rng.choice((0.5, 1.0, 3.0, 7.0)))))
    return script


def drive_durable(make_keeper, script, clock):
    """把含 crash/grantq/parallel 的脚本喂给 DurableLeaseKeeper。

    make_keeper(journal) 负责按日志造台：首条 crash 前用新内存日志，
    crash 后用 recover 从同一日志重放。回执统一成可直接比较的形态：
    租约是字段元组，撞车 None，parallel 是按路数排序的回执列表。
    """
    journal = None
    keeper = make_keeper(None)
    receipts = []
    for event in script:
        kind = event[0]
        if kind == "crash":
            keeper = make_keeper(keeper.journal)
            receipts.append("crashed")
        elif kind == "grantq":
            _, resource, holder, ttl, request_id = event
            try:
                lease = keeper.grant(
                    resource, holder, ttl, request_id=request_id
                )
            except LeaseConflict:
                receipts.append(None)
            else:
                receipts.append(as_tuple(lease))
        elif kind == "parallel":
            _, resource, holder, ttl, request_id, ways = event
            barrier = threading.Barrier(ways)
            box = [None] * ways

            def attempt(index):
                barrier.wait()
                try:
                    box[index] = as_tuple(
                        keeper.grant(
                            resource, holder, ttl, request_id=request_id
                        )
                    )
                except LeaseConflict:
                    box[index] = None

            workers = [
                threading.Thread(target=attempt, args=(i,)) for i in range(ways)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            receipts.append(list(box))
        elif kind == "renew":
            _, resource, holder, ttl = event
            lease_id = _current(keeper, resource, holder)
            result = (
                None if lease_id is None
                else keeper.renew(lease_id, holder, ttl)
            )
            receipts.append(None if result is None else as_tuple(result))
        elif kind == "release":
            _, resource, holder = event
            lease_id = _current(keeper, resource, holder)
            receipts.append(
                False if lease_id is None
                else keeper.release(lease_id, holder)
            )
        else:
            receipts.append(clock.advance(event[1]))
    return receipts


def model_durable(script, start=0.0):
    """纯模型对拍 DurableLeaseKeeper：幂等发放、并发同标识、日志恢复。

    committed 记每资源最后一条已落日志的发放快照；released 记已归还的
    lease_id；state 是当前内存活态；dedupe 把 request_id 钉到快照或
    "conflict"；high 记每资源历史最大记号。续期不改 committed，崩溃按
    发号时的原始到期时刻决定续活还是回收。
    """
    now = start
    token = 0
    committed = {}
    released = set()
    state = {}
    dedupe = {}
    high = {}
    receipts = []

    for event in script:
        kind = event[0]
        if kind == "crash":
            restored = {}
            for resource, snapshot in committed.items():
                if snapshot["lease_id"] in released:
                    continue
                if snapshot["expires_at"] <= now:
                    continue
                restored[resource] = dict(snapshot)
            state = restored
            receipts.append("crashed")
            continue
        if kind in ("grantq", "parallel"):
            resource, holder, ttl = event[1], event[2], event[3]
            request_id = event[4]

            def one_grant():
                nonlocal token
                cached = dedupe.get(request_id)
                if cached is not None:
                    if cached == "conflict":
                        return None
                    if (cached["resource"], cached["holder"], cached["ttl"]) != (
                        resource, holder, ttl
                    ):
                        raise ValueError(
                            "request_id %r reused with different parameters"
                            % (request_id,)
                        )
                    return _tuple_of(cached)
                current = state.get(resource)
                if current is not None and now < current["expires_at"]:
                    dedupe[request_id] = "conflict"
                    return None
                token += 1
                snapshot = {
                    "lease_id": "L%06d" % token,
                    "resource": resource,
                    "holder": holder,
                    "token": token,
                    "ttl": ttl,
                    "expires_at": now + ttl,
                }
                committed[resource] = snapshot
                state[resource] = dict(snapshot)
                dedupe[request_id] = snapshot
                high[resource] = token
                return _tuple_of(snapshot)

            if kind == "parallel":
                # 同一把锁把并发路数串行化，结果与调度次序无关：
                # 第一发决定一切，其余路要么拿同一份，要么一起撞车。
                receipts.append([one_grant() for _ in range(event[5])])
            else:
                receipts.append(one_grant())
            continue
        if kind == "renew":
            _, resource, holder, ttl = event
            current = state.get(resource)
            if (current is None or current["holder"] != holder
                    or now >= current["expires_at"]):
                receipts.append(None)
                continue
            extend = current["ttl"] if ttl is None else ttl
            current["ttl"] = extend
            current["expires_at"] = now + extend
            receipts.append(_tuple_of(current))
        elif kind == "release":
            _, resource, holder = event
            current = state.get(resource)
            if (current is not None and current["holder"] == holder
                    and now < current["expires_at"]):
                released.add(current["lease_id"])
                del state[resource]
                receipts.append(True)
            else:
                receipts.append(False)
        else:
            now += event[1]
            receipts.append(now)
    final = {
        "holders": {
            resource: (
                state[resource]["holder"]
                if resource in state and now < state[resource]["expires_at"]
                else None
            )
            for resource in committed
        },
        "last_token": token,
        "high_water": dict(high),
    }
    return receipts, final
