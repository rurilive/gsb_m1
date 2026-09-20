"""fairlease 现场复现：饥饿、同级乱序、撤单不生效、超时边界。

每个场景用注入时钟把时刻摆准，打印实际结果并与约定对照。
"""

from fairlease.lease import FairLease


class FakeClock:
    def __init__(self, t=0.0):
        self.now = float(t)

    def __call__(self):
        return self.now


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
    print("  逐拍发放 ->", served)
    print("  batch 被发放的时刻(拍) ->", served.index("batch") + 1)
    print("  期望：第 5 拍 batch 等够 aging，这一拍发给它")
    print("  结论：", "OK" if served ==
          ["hot1", "hot2", "hot3", "hot4", "batch", "hot5"] else "FAIL")


def scenario_same_priority():
    print("=== 场景二：同优先级里先到的反而排在后面 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    fl.request("zeta", 2)               # 先到
    fl.request("alpha", 2)              # 后到
    result = [fl.grant(), fl.grant()]
    print("  依次发放 ->", result)
    print("  期望：先到先得，顺序为 ['zeta', 'alpha']")
    print("  结论：", "OK" if result == ["zeta", "alpha"] else "FAIL")


def scenario_cancel():
    print("=== 场景三：撤掉的请求照样把租约领走 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    doomed = fl.request("ghost", 0)     # 高优先级，随后被撤
    fl.request("real", 5)
    print("  cancel(ghost) ->", fl.cancel(doomed))
    pending = fl.pending()
    granted = fl.grant()
    print("  撤单后 pending ->", pending)
    print("  grant() ->", granted)
    print("  期望：pending 只剩 ['real']，grant 发的是 'real'")
    print("  结论：", "OK" if pending == ["real"] and granted == "real"
          else "FAIL")


def scenario_timeout_edge():
    print("=== 场景四：恰好卡在超时上限被误杀 ===")
    clock = FakeClock(0.0)
    fl = FairLease(clock=clock, aging=5.0)
    fl.request("edge", 1, timeout=2.0)
    clock.now = 2.0
    edge = fl.grant()
    print("  等满 timeout 整点，grant() ->", edge)
    print("  期望：'edge'，约定是超过 timeout 才作废")
    print("  结论：", "OK" if edge == "edge" else "FAIL")

    clock2 = FakeClock(0.0)
    fl2 = FairLease(clock=clock2, aging=5.0)
    fl2.request("late", 1, timeout=2.0)
    clock2.now = 2.5
    late = fl2.grant()
    print("  真超时到 t=2.5，grant() ->", late)
    print("  期望：None，超出上限的请求该丢掉")
    print("  结论：", "OK" if late is None else "FAIL")


def main():
    scenario_starvation()
    print()
    scenario_same_priority()
    print()
    scenario_cancel()
    print()
    scenario_timeout_edge()


if __name__ == "__main__":
    main()
