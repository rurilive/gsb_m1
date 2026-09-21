"""idemkey 修复后演示：原先重复扣款的几档怪事现在都兜得住。

逐段演示：
  1. 只差大小写的两个单号被当成两笔，各拿各的回执
  2. 服务重启后结果还在，重发正确回放老回执
  3. 处理中途失败用 release 放开占位，重发可以重新开工
  4. 有效期按完成时刻起算，长流程中途 renew 续期也不必重跑
  5. 结果体积超上限落成截断标记，取回时看得出被截断过
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
    print("=== 1. 只差大小写的两个单号现在按两笔算 ===")
    store = IdempotencyStore()
    print("  begin('Order-7001') ->", store.begin("Order-7001"))
    store.finish("Order-7001", {"order": "Order-7001", "amount": 100})
    print("  Order-7001 收工，收款 100")
    print("  begin('order-7001') ->", store.begin("order-7001"),
          "（新单，正常开工）")
    store.finish("order-7001", {"order": "order-7001", "amount": 200})
    print("  get('order-7001')   ->", store.get("order-7001"),
          "（拿回的是本单自己的回执）")
    print("  get('Order-7001')   ->", store.get("Order-7001"),
          "（大小写两单互不串台）")


def demo_restart_loses_results():
    print("\n=== 2. 服务重启后结果原样找回 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        before = IdempotencyStore(path=path)
        before.begin("pay-88")
        before.finish("pay-88", {"amount": 250, "state": "paid"})
        print("  重启前 get('pay-88')  ->", before.get("pay-88"))
        after = IdempotencyStore(path=path)
        print("  重启后 get('pay-88')  ->", after.get("pay-88"),
              "（回执完整找回）")
        print("  重启后 begin('pay-88')->", after.begin("pay-88"),
              "（重发正确判成重复，转去回放而不是再扣一次）")
        print("  重发直接回放         ->", after.get("pay-88"))


def demo_halfway_failure():
    print("\n=== 3. 处理中途失败，release 后重发能重新开工 ===")
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
        except RuntimeError:
            store.release(order)     # 没干完就把占位放开
            raise
        store.finish(order, result)
        return result

    try:
        submit("pay-99")
    except RuntimeError as exc:
        print("  第一次提交失败:", exc)
    print("  同一笔重发拿回:", submit("pay-99"),
          "（release 放开占位后，第二次正常收款）")


def demo_expiry_from_begin():
    print("\n=== 4. 有效期按完成时刻起算，长流程可中途续期 ===")
    clock = FakeClock()
    store = IdempotencyStore(ttl=60, clock=clock)
    store.begin("pay-77")
    clock.advance(90)                 # 这单前后跑了 90 秒
    store.finish("pay-77", {"amount": 300})
    print("  ttl=60，这单从开工到收工花了 90 秒")
    print("  finish 之后马上 get('pay-77') ->", store.get("pay-77"),
          "（从收工时刻重算 60 秒，结果还在）")
    clock.advance(59)
    print("  收工后再过 59 秒 get ->", store.get("pay-77"), "（仍在有效期）")

    clock2 = FakeClock()
    long_store = IdempotencyStore(ttl=60, clock=clock2)
    long_store.begin("pay-78")
    clock2.advance(40)
    print("\n  另一单 ttl=60，跑了 40 秒时 renew 续期")
    print("  renew('pay-78') ->", long_store.renew("pay-78"))
    clock2.advance(40)
    print("  续期后又跑了 40 秒，begin('pay-78') ->",
          long_store.begin("pay-78"), "（False：占位还在，不会重跑）")
    long_store.finish("pay-78", {"amount": 88})
    print("  收工回执 ->", long_store.get("pay-78"))


def demo_oversize_result():
    print("\n=== 5. 结果超上限落成截断标记 ===")
    store = IdempotencyStore(max_result_size=64)
    big = {"receipt": "x" * 200}
    store.begin("pay-66")
    stored = store.finish("pay-66", big)
    print("  写入一个超长回执，取回 ->", stored)
    print("  truncated 标记:", stored.truncated,
          "原始大小:", stored.original_size, "上限:", stored.max_size)
    print("  重启后从磁盘读回仍是截断标记 ->", end=" ")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idem.json")
        persisted = IdempotencyStore(path=path, max_result_size=64)
        persisted.begin("pay-66")
        persisted.finish("pay-66", big)
        reloaded = IdempotencyStore(path=path, max_result_size=64)
        print(reloaded.get("pay-66"))


def main():
    demo_case_collision()
    demo_restart_loses_results()
    demo_halfway_failure()
    demo_expiry_from_begin()
    demo_oversize_result()
    print("\n演示结束")


if __name__ == "__main__":
    main()
