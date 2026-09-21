"""确定性事件脚本：生成、驱动、纯模型对拍三件套。

脚本是 (事件名, ...) 元组串：grant、renew、release 对某资源某持有者
下手，sleep 把假时钟往前拨。make_script 按 seed 生成，同 seed 一字不
差；drive 把脚本喂给真实现逐条跑，记下每条回执；model_run 不碰任何真
对象，在纸上把同一份脚本再跑一遍，算出逐条回执与终局。两边用 as_tuple
抹平类型后逐条对得上，实现才算没跑偏。
"""

import random

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
