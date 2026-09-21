"""idemkey 现状演示：幂等键没兜住重复扣款的几类现象。

逐段演示四个现象：
  1. 只差大小写的两个单号被当成同一笔，后一笔拿回前一单的回执
  2. 服务重启后键还在、结果没了，重发被判成重复
  3. 处理中途失败，键从此卡死，永远回一份空结果
  4. 耗时请求刚写完结果，还没到有效期就被清掉
"""

import os
import tempfile

from idemkey import IdempotencyStore


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def demo_case_collision():
    print("=== 1. 大小写不同的两个单号被并成一笔 ===")
    store = IdempotencyStore()
    print("  begin('Order-7001') ->", store.begin("Order-7001"))
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  Order-7001 收工，收款 100")
    print("  begin('order-7001') ->", store.begin("order-7001"),
          "（这是一笔新单，本该开工）")
    print("  get('order-7001')   ->", store.get("order-7001"),
          "（拿回的是另一笔单子的回执）")


def demo_restart_loses_results():
    print("\n=== 2. 服务重启后键还在、结果没了 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path)
        print("  重启后 get('pay-88')  ->", after.get("pay-88"), "（结果丢了）")
        print("  重启后 begin('pay-88')->", after.begin("pay-88"),
              "（键还在，重发被判成重复）")


def demo_halfway_failure():
    print("\n=== 3. 处理中途失败，键被卡死 ===")
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
          "（被判成已处理，回一份空结果，再也发不出去）")


def demo_expiry_from_begin():
    print("\n=== 4. 耗时请求的结果还没焐热就被清掉 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（记录按开工时刻算，早被清掉了）")


def main():
    demo_case_collision()
    demo_restart_loses_results()
    demo_halfway_failure()
    demo_expiry_from_begin()
    print("\n演示结束")


if __name__ == "__main__":
    main()
