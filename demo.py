"""tracectx 现状演示。

第一段：一批模拟记录并行校验，坏记录被隔离，不拖垮整批。
第二段：后台单任务的两种用法（等待 / 回调）。
第三段：跨线程调用链——一条链路一个 id，分段计时，收尾打印树形报告。
"""

import threading
import time

from tracectx import (
    ItemFailure,
    async_call,
    begin_chain,
    correlation_id,
    first_failure,
    map_batch,
    run_detached,
    set_slow_threshold,
    span,
)

CURRENCIES = {"CNY", "USD", "EUR"}

RECORDS = [
    {"id": "r001", "amount": 12900, "currency": "CNY"},
    {"id": "r002", "amount": 4500, "currency": "USD"},
    {"id": "r003", "amount": -1, "currency": "EUR"},
    {"id": "r004", "amount": 880, "currency": "JPY"},
    {"id": "r005", "amount": 77700, "currency": "CNY"},
    {"id": "r006", "amount": 6600, "currency": "EUR"},
    {"id": "r007", "amount": 990, "currency": "USD"},
    {"id": "r008", "amount": 12300, "currency": "CNY"},
    {"id": "r009", "amount": 450, "currency": "USD"},
    {"id": "r010", "amount": 51000, "currency": "CNY"},
]


def verify(rec):
    """校验单条记录，纯计算，返回带校验和的结果。"""
    if rec["currency"] not in CURRENCIES:
        raise ValueError("unsupported currency: %s" % rec["currency"])
    if rec["amount"] <= 0:
        raise ValueError("non-positive amount")
    x = 7
    for ch in rec["id"]:
        x = (x * 31 + ord(ch)) % 99991
    for _ in range(2000):  # 模拟一点计算量
        x = (x * 1103515245 + 12345) % 2147483648
    return {"id": rec["id"], "checksum": x}


def main():
    print("=== 并行校验一批记录（workers=3） ===")
    results = map_batch(verify, RECORDS, workers=3)
    ok = [r for r in results if not isinstance(r, ItemFailure)]
    bad = [r for r in results if isinstance(r, ItemFailure)]
    print("  通过 %d 条，失败 %d 条" % (len(ok), len(bad)))
    f = first_failure(results)
    if f is not None:
        print("  首个失败: %s -> %s" % (f.item["id"], f.error))
    for r in ok[:3]:
        print("  %s checksum=%d" % (r["id"], r["checksum"]))

    print("\n=== 后台单任务 ===")
    summary = run_detached(lambda: "ok=%d bad=%d" % (len(ok), len(bad)))
    print("  run_detached 返回:", summary)

    done = threading.Event()
    t = async_call(
        lambda: sum(r["checksum"] for r in ok),
        on_done=lambda v: (print("  async_call 汇总:", v), done.set()),
    )
    done.wait(5)
    t.join(5)

    print("\n=== 调用链追踪（一条链路一个 id，跨线程计时） ===")
    set_slow_threshold(0.005)  # 演示用：5ms 以上算慢

    def traced_verify(rec):
        with span("verify %s" % rec["id"]):
            if rec["id"] == "r005":
                time.sleep(0.02)  # 模拟一条慢记录
            return verify(rec)

    with begin_chain() as chain:
        print("  correlation-id:", correlation_id())
        with span("verify-batch"):
            map_batch(traced_verify, RECORDS, workers=3)
        with span("summarize"):
            run_detached(lambda: "ok=%d bad=%d" % (len(ok), len(bad)))
    print("  链路报告:")
    for line in chain.report().splitlines()[1:]:
        print("   ", line)


if __name__ == "__main__":
    main()
