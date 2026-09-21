"""idemkey 现象演示：四类事故的病根与修后行为，外加两个新能力。

每段先复述线上曾经出问题的现象（旧实现的病根），再用修后的库演示
现在的正确表现：
  1. 只差大小写的两个单号不再并成一笔
  2. 服务重启后结果跟着键一起回来（注意落盘要配跨重启稳定的时钟）
  3. 处理中途失败用 rollback 放开占位，重发能正常扣款
  4. 有效期从完成时刻起算，耗时请求收工即取得到
  5. renew：长流程中途续期，不必整单重跑
  6. 结果超过体积上限时落成截断标记
"""

import os
import tempfile

from idemkey import IdempotencyStore, TruncatedResult


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def demo_case_collision():
    print("=== 1. 大小写不同的两个单号 ===")
    print("  病根：旧 _normalize 把键统一 lower()，'Order-7001' 与")
    print("        'order-7001' 折成同一个键，后一笔拿回前一笔的回执，")
    print("        运营误以为没扣上又补发，用户被多扣。")
    store = IdempotencyStore()
    print("  begin('Order-7001') ->", store.begin("Order-7001"))
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  Order-7001 收工，收款 100")
    print("  begin('order-7001') ->", store.begin("order-7001"),
          "（新单正常开工）")
    store.finish("order-7001", {"order": "order-7001", "amount": 80})
    print("  get('Order-7001')   ->", store.get("Order-7001"))
    print("  get('order-7001')   ->", store.get("order-7001"),
          "（两笔各回各的回执；首尾空白仍会被 trim）")


def demo_restart_loses_results():
    print("\n=== 2. 服务重启后结果跟着键回来 ===")
    print("  病根：旧 finish 只改内存不 _save，落盘的只有 begin 写下的空")
    print("        占位。重启后键还在、结果是 None，重发全被判重复卡住。")
    print("        （落盘场景请配跨重启稳定的时钟，例如 time.time；")
    print("         time.monotonic 每次重启会重新起算，只适用于纯内存。）")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        tick = FakeClock()
        before = IdempotencyStore(path=path, clock=tick, ttl=3600)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path, clock=tick, ttl=3600)
        print("  重启后 get('pay-88')  ->", after.get("pay-88"), "（结果还在）")
        print("  重启后 begin('pay-88')->", after.begin("pay-88"),
              "（正确判重复，回放上面的回执即可）")

        # 旧实现还会把“半截子占位”带过重启：begin 后崩溃，重启后这个
        # 键既取不到结果也永远不能重开。新实现加载时丢弃未 finish 的
        # 占位，让它能重新处理。
        before.begin("pay-89")
        recovered = IdempotencyStore(path=path, clock=tick, ttl=3600)
        print("  begin 后崩溃的 pay-89，重启后 begin ->",
              recovered.begin("pay-89"), "（占位不再跨重启卡死）")


def demo_halfway_failure():
    print("\n=== 3. 处理中途失败，rollback 后能重发 ===")
    print("  病根：begin 先占键，下游超时没走到 finish，空占位永远留着；")
    print("        重发 begin=False、get=None，单子从此发不出去。")
    store = IdempotencyStore()
    attempts = {"n": 0}

    def do_work(order):
        attempts["n"] += 1
        if attempts["n"] == 1:            # 第一次下游抖了一下
            raise RuntimeError("下游超时，这一单没做完")
        return {"order": order, "state": "paid"}

    def submit(order):
        if not store.begin(order):
            return store.get(order)
        try:
            result = do_work(order)
        except Exception:
            store.rollback(order)      # 没做完就把占位放开
            raise
        store.finish(order, result)
        return result

    try:
        submit("pay-99")
    except RuntimeError as exc:
        print("  第一次提交失败:", exc)
    print("  直接重发（内部重新 begin）拿回:", submit("pay-99"),
          "（占位已放开，第二次正常扣款成功）")


def demo_expiry_from_finish():
    print("\n=== 4. 有效期从完成时刻起算 ===")
    print("  病根：旧 _purge 用 now - created_at >= ttl，TTL 从开工占键")
    print("        时刻算。单子跑得比 TTL 久，finish 完立刻 get 就被清掉，")
    print("        离“完成后存活 60 秒”的约定还早。")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（从收工时刻起算，结果取得到）")
    clock.advance(59)
    print("  收工后再过 59 秒 get ->", store.get("pay-77"), "（仍在有效期）")
    clock.advance(2)
    print("  收工后累计 61 秒 get ->", store.get("pay-77"), "（到期后才清空）")


def demo_renew():
    print("\n=== 5. renew：长流程中途续期 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-66")
    clock.advance(50)
    print("  开工 50 秒、处理未完，renew(ttl=120) ->",
          store.renew("pay-66", ttl=120))
    clock.advance(100)
    store.finish("pay-66", {"amount": 500})
    print("  续期后又跑了 100 秒才 finish，马上 get ->", store.get("pay-66"),
          "（没有中途过期，也不必重跑）")
    clock.advance(55)
    print("  完成 55 秒后（默认窗口还剩 5 秒）renew(ttl=120) ->",
          store.renew("pay-66", ttl=120), "（从完成时刻起续到 +120 秒）")
    clock.advance(55)
    print("  完成累计 110 秒后 get ->", store.get("pay-66"),
          "（早已越过默认 60 秒窗口，续期生效）")
    print("  对不存在的键 renew ->", store.renew("nope"))


def demo_truncation():
    print("\n=== 6. 结果超过体积上限落成截断标记 ===")
    store = IdempotencyStore(max_result_size=64)
    store.finish("small", {"state": "paid"})
    print("  小结果原样取回 ->", store.get("small"))
    store.finish("big", {"state": "paid", "receipt": "X" * 200})
    marker = store.get("big")
    print("  超大结果取回   ->", marker)
    print("  isinstance 截断标记 ->", isinstance(marker, TruncatedResult),
          "（调用方据此走对账补查，不把标记当回执回放）")


def demo_truncation_round_trip():
    print("\n=== 7. 截断标记重启后仍是标记 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path, max_result_size=32)
        before.finish("big", {"receipt": "Y" * 100})
        after = IdempotencyStore(path=path, max_result_size=32)
        print("  重启后 get('big') ->", after.get("big"))


def main():
    demo_case_collision()
    demo_restart_loses_results()
    demo_halfway_failure()
    demo_expiry_from_finish()
    demo_renew()
    demo_truncation()
    demo_truncation_round_trip()
    print("\n演示结束：四类病根均已修复，续期与截断能力可用。")


if __name__ == "__main__":
    main()
