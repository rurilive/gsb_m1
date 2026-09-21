"""带并发重试与崩溃重启的确定性脚本对拍。

在 script 三件套的基础上加三种事件：grant 带请求标识（重试沿用同一
标识，必须拿回同一份租约）、burst 并发重试（k 个线程同一标识同时发
放，全员必须拿回同一份）、crash 崩溃重启（同一本日志重开发放台，记
号续发、未归还租约回收、高水位回灌闸门）。make_dscript 按 seed 生成，
drive_durable 喂给真实现，model_durable 纸上重算，回执逐条比对。
"""

import random
import threading

from leasekeeper.keeper import LeaseConflict
from leasekeeper.script import as_tuple


def make_dscript(seed, resources=("db.primary",), steps=160,
                 holders=("n1", "n2", "n3")):
    """按 seed 生成 steps 条事件：发放、重试、并发重试、续期、归还、
    崩溃与拨钟。重试从最近发出的请求标识里挑，模拟客户端重发。"""
    rng = random.Random(seed)
    script = []
    issued = []
    counter = 0
    for _ in range(steps):
        roll = rng.random()
        resource = rng.choice(resources)
        holder = rng.choice(holders)
        if roll < 0.30 or roll < 0.44 and not issued:
            counter += 1
            req = "req-%04d" % counter
            ttl = float(rng.choice((2.0, 5.0, 9.0)))
            issued.append((req, resource, holder, ttl))
            del issued[:-8]
            script.append(("grant", resource, holder, ttl, req))
        elif roll < 0.38:
            req, resource, holder, ttl = rng.choice(issued)
            script.append(("grant", resource, holder, ttl, req))
        elif roll < 0.44:
            counter += 1
            req = "req-%04d" % counter
            ttl = float(rng.choice((2.0, 5.0, 9.0)))
            issued.append((req, resource, holder, ttl))
            del issued[:-8]
            script.append(
                ("burst", resource, holder, ttl, req, rng.choice((2, 3, 4)))
            )
        elif roll < 0.72:
            script.append(("renew", resource, holder, rng.choice((None, 4.0))))
        elif roll < 0.86:
            script.append(("release", resource, holder))
        elif roll < 0.90:
            script.append(("crash",))
        else:
            script.append(("sleep", float(rng.choice((0.5, 1.0, 3.0, 7.0)))))
    return script


def drive_durable(boot, script, clock):
    """把脚本逐条喂给真实现，返回 (回执列表, 最后一台发放台)。

    boot() 建发放台，crash 事件再调一次表示崩溃重启（同一本日志、同
    一台闸门）。burst 用真线程并发发同一请求标识，回执是各线程拿到的
    租约元组；crash 回执是重启后的最后记号，专门验续号。
    """
    keeper = boot()
    receipts = []
    for event in script:
        kind = event[0]
        if kind == "grant":
            _, resource, holder, ttl, req = event
            receipts.append(_grant(keeper, resource, holder, ttl, req))
        elif kind == "burst":
            _, resource, holder, ttl, req, count = event
            results = [None] * count
            workers = [
                threading.Thread(
                    target=_burst_one,
                    args=(keeper, resource, holder, ttl, req, results, i),
                )
                for i in range(count)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            receipts.append(tuple(results))
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
        elif kind == "crash":
            keeper = boot()
            receipts.append(keeper.stats().last_token)
        else:
            receipts.append(clock.advance(event[1]))
    return receipts, keeper


def model_durable(script, start=0.0):
    """纯模型在纸上跑同一份脚本，返回 (逐条回执, 终局)。

    记号与台账在 crash 后保留（日志还在），活租约与幂等台账在 crash
    后清空（一律回收）。终局带 holders、grants、last_token 与各资源
    高水位 water。
    """
    now = start
    token = 0
    state = {}
    by_id = {}
    reqs = {}
    water = {}
    seen = []
    grants = 0
    receipts = []

    def grant(resource, holder, ttl, req):
        nonlocal token, grants
        if req in reqs:
            lease = by_id.get(reqs[req])
            if lease is not None and now < lease["expires_at"]:
                return lease
            del reqs[req]
        current = state.get(resource)
        if current is not None and now < current["expires_at"]:
            return None
        token += 1
        lease = {
            "lease_id": "L%06d" % token,
            "resource": resource,
            "holder": holder,
            "token": token,
            "ttl": ttl,
            "expires_at": now + ttl,
        }
        state[resource] = lease
        by_id[lease["lease_id"]] = lease
        reqs[req] = lease["lease_id"]
        if token > water.get(resource, 0):
            water[resource] = token
        grants += 1
        return lease

    for event in script:
        kind = event[0]
        if kind == "grant":
            _, resource, holder, ttl, req = event
            if resource not in state and resource not in seen:
                seen.append(resource)
            receipts.append(as_tuple(grant(resource, holder, ttl, req)))
        elif kind == "burst":
            _, resource, holder, ttl, req, count = event
            if resource not in state and resource not in seen:
                seen.append(resource)
            lease = grant(resource, holder, ttl, req)
            receipts.append(tuple(as_tuple(lease) for _ in range(count)))
        elif kind == "renew":
            _, resource, holder, ttl = event
            current = state.get(resource)
            if (current is None or current["holder"] != holder
                    or now >= current["expires_at"]):
                if current is not None and now >= current["expires_at"]:
                    del state[resource]
                    by_id.pop(current["lease_id"], None)
                receipts.append(None)
                continue
            extend = current["ttl"] if ttl is None else ttl
            current = dict(current, ttl=extend, expires_at=now + extend)
            state[resource] = current
            by_id[current["lease_id"]] = current
            receipts.append(as_tuple(current))
        elif kind == "release":
            _, resource, holder = event
            current = state.get(resource)
            if (current is not None and current["holder"] == holder
                    and now < current["expires_at"]):
                del state[resource]
                by_id.pop(current["lease_id"], None)
                receipts.append(True)
            else:
                receipts.append(False)
        elif kind == "crash":
            state.clear()
            by_id.clear()
            reqs.clear()
            receipts.append(token)
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
        "grants": grants,
        "last_token": token,
        "water": dict(water),
    }
    return receipts, final


def as_dtuple(receipt):
    """把回执抹成可比较的形态：burst 的租约元组递归抹平，其余同
    script.as_tuple。"""
    if isinstance(receipt, (tuple, list)):
        return tuple(as_dtuple(r) for r in receipt)
    return as_tuple(receipt)


def _grant(keeper, resource, holder, ttl, req):
    try:
        return keeper.grant(resource, holder, ttl, request_id=req)
    except LeaseConflict:
        return None


def _burst_one(keeper, resource, holder, ttl, req, results, index):
    results[index] = _grant(keeper, resource, holder, ttl, req)


def _current(keeper, resource, holder):
    lease = keeper.get(resource)
    if lease is None or lease.holder != holder:
        return None
    return lease.lease_id
