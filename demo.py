"""fairlease 四个线上现场的复现与修复验证。

每个场景用注入时钟把时刻摆准，打印实际结果并与修复后的契约对照，
最后一行给出通过/失败汇总。直接运行：python3 demo.py
"""

from fairlease.lease import FairLease


class FakeClock:
    def __init__(self, t=0.0):
        self.now = float(t)

    def __call__(self):
        return self.now


RESULTS = []


def check(name, actual, expected):
    ok = actual == expected
    RESULTS.append((name, ok))
    print(f"  实际 -> {actual!r}")
    print(f"  期望 -> {expected!r}")
    print(f"  {'[通过]' if ok else '[失败]'} {name}")


def scenario_starvation():
    print("=== 场景一：高优先级持续涌入，低优先级颗粒无收 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    fl.request("batch", 9)              # 低优先级，先到
    served = []
    for t in range(1, 7):
        clock.now = float(t)
        fl.request(f"hot{t}", 0)        # 每拍都来一个高优先级
        served.append(fl.grant())
    # 第 5 拍 batch 等够 aging=5，老化组整组压过新来的高优先级
    check("等够 aging 的第 5 拍发放 batch", served,
          ["hot1", "hot2", "hot3", "hot4", "batch", "hot5"])
    check("batch 已离队，不再 pending", "batch" in fl.pending(), False)

    # 更强的保证：无论高优先级涌入多久，老化后的下一拍必被服务
    clock2 = FakeClock(0.0)
    fl2 = FairLease(clock=clock2, aging=3.0)
    fl2.request("batch", 9)
    served_at = None
    for t in range(1, 100):
        clock2.now = float(t)
        fl2.request(f"hot{t}", 0)
        if fl2.grant() == "batch":
            served_at = t
            break
    check("持续涌入 99 拍内 batch 仍在第 3 拍被发放", served_at, 3)


def scenario_same_priority():
    print("=== 场景二：同优先级里先到的反而排在后面 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    fl.request("zeta", 2)               # 先到
    fl.request("alpha", 2)              # 后到
    fl.request("mid", 2)
    check("同优先级严格先来后到", [fl.grant(), fl.grant(), fl.grant()],
          ["zeta", "alpha", "mid"])


def scenario_cancel():
    print("=== 场景三：撤掉的请求照样把租约领走 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    doomed = fl.request("ghost", 0)     # 高优先级，随后被撤
    fl.request("real", 5)
    check("cancel 返回 True", fl.cancel(doomed), True)
    check("撤单立即出队", fl.pending(), ["real"])
    check("下一轮 grant 发给 real", fl.grant(), "real")
    check("已撤的 ticket 再撤返回 False", fl.cancel(doomed), False)


def scenario_timeout_edge():
    print("=== 场景四：恰好卡在超时上限被误杀 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    fl.request("edge", 1, timeout=2.0)
    clock.now = 2.0
    check("恰好等满 timeout 仍然有效", fl.grant(), "edge")

    clock2 = FakeClock(0.0)
    fl2 = FairLease(clock=clock2, aging=5.0)
    fl2.request("late", 1, timeout=2.0)
    clock2.now = 2.5
    check("超过 timeout 才作废", fl2.grant(), None)

    clock3 = FakeClock(0.0)
    fl3 = FairLease(clock=clock3, aging=5.0)
    fl3.request("hair", 1, timeout=2.0)
    clock3.now = 2.0000001
    check("超出一微秒也作废", fl3.pending(), [])


def main():
    scenario_starvation()
    print()
    scenario_same_priority()
    print()
    scenario_cancel()
    print()
    scenario_timeout_edge()
    print()
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    print(f"=== 汇总：{passed}/{total} 项契约符合预期 ===")
    if passed != total:
        for name, ok in RESULTS:
            if not ok:
                print(f"  未通过：{name}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
