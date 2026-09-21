"""idemkey 修复后行为演示：对账出的几类怪事现在都兜住了。

逐段演示：
  1. 只差大小写的两个单号是两笔独立的单，各拿各的回执
  2. 服务重启后结果跟着盘回来，重发正确回放、不再判重复
  3. 处理中途失败不会留下死键，重发能正常重新处理
  4. 有效期从收工时刻起算，长流程的单子不会刚写完就过期
  5. 收工时刻续期：有效期在 finish 时刷新，不必为续期重跑
  6. 结果超体积上限只落截断标记，取回时可识别被截断过
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
    print("=== 1. 大小写不同的两个单号是两笔单 ===")
    store = IdempotencyStore()
    print("  begin('Order-7001') ->", store.begin("Order-7001"))
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  Order-7001 收工，收款 100")
    print("  begin('order-7001') ->", store.begin("order-7001"),
          "（新单正常开工，不再并单）")
    store.finish("order-7001", {"order": "order-7001", "amount": 200})
    print("  get('Order-7001')   ->", store.get("Order-7001"),
          "（大小写单各回放各的回执）")
    print("  get('order-7001')   ->", store.get("order-7001"))


def demo_restart_loses_results():
    print("\n=== 2. 服务重启后结果跟着盘回来 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path)
        print("  重启后 get('pay-88')  ->", after.get("pay-88"),
              "（结果完整盘回）")
        print("  重启后 begin('pay-88')->", after.begin("pay-88"),
              "（已处理，正确判重复并回放）")


def demo_halfway_failure():
    print("\n=== 3. 处理中途失败，重发能正常补做 ===")
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
        result = do_work(order)
        store.finish(order, result)
        return result

    try:
        submit("pay-99")
    except RuntimeError as exc:
        print("  第一次提交失败:", exc)
    print("  同一笔重发拿回:", submit("pay-99"),
          "（残键不挡重入，这次真正收工）")
    print("  再重发 begin     ->", store.begin("pay-99"),
          "（已处理，判重复）")


def demo_expiry_from_begin():
    print("\n=== 4. 有效期从收工时刻起算，长请求不会刚写完就过期 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（处理耗时不算进有效期）")
    clock.advance(59)
    print("  收工后再过 59 秒 get           ->", store.get("pay-77"),
          "（离完成还没满 60 秒，仍在）")
    clock.advance(1)
    print("  收工满 60 秒后 get             ->", store.get("pay-77"),
          "（按完成时刻正常过期，键可重处理）")
    print("  此时 begin('pay-77')           ->", store.begin("pay-77"))


def demo_ttl_renewed_at_finish():
    print("\n=== 5. 收工时刻续期：中途再久也不必为重跑预留窗口 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=30, clock=clock)
    store.begin("pay-66")
    clock.advance(20)                 # 已经跑了 20 秒
    print("  ttl=30，开跑 20 秒，单子还在处理中，无需重跑续期")
    clock.advance(20)                 # 又跑了 20 秒才收工
    store.finish("pay-66", {"amount": 500})
    print("  共耗时 40 秒才 finish；收工后再过 29 秒：")
    clock.advance(29)
    print("  get('pay-66') ->", store.get("pay-66"),
          "（有效期自收工重新起算 30 秒，完成即续期）")


def demo_oversize_result_is_truncated():
    print("\n=== 6. 结果超上限只落截断标记 ===")
    store = IdempotencyStore(max_result_size=64)
    big = {"items": ["x" * 40, "y" * 40]}
    stored = store.finish("pay-55", big)
    print("  finish 大结果后返回:", stored)
    replayed = store.get("pay-55")
    print("  get('pay-55')      ->", replayed)
    print("  是否被截断过:", isinstance(replayed, TruncatedResult),
          "；原始大小:", replayed.size, "字节；上限:", replayed.limit, "字节")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        persisted = IdempotencyStore(path=path, max_result_size=64)
        persisted.finish("pay-55", big)
        rebooted = IdempotencyStore(path=path, max_result_size=64)
        print("  重启后取回:", rebooted.get("pay-55"),
              "（截断标记同样能盘回来）")

    small = {"ok": True}
    store.finish("pay-56", small)
    print("  正常小结果不受影响:", store.get("pay-56"))


def main():
    demo_case_collision()
    demo_restart_loses_results()
    demo_halfway_failure()
    demo_expiry_from_begin()
    demo_ttl_renewed_at_finish()
    demo_oversize_result_is_truncated()
    print("\n演示结束")


if __name__ == "__main__":
    main()
