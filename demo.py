"""centledger 修复后演示：按财务口径把各类场景直接跑出来。

均摊尾差归权重最大（并列取账户名靠前）的户；退款对冲批里零权重
账户不动；分批跑账面与请求总额始终对齐；比一分小的请求直接报错；
同一批重放返回首次结果，输出逐字节稳定；大额入账一分不差。
"""

import random
import sys
import time

from centledger import (
    BatchRequest, Ledger, MoneyError, allocate, format_cents, from_cents,
)


def section(title):
    print("=== %s ===" % title)


def even_split_tail():
    section("均摊尾差：归权重最大、账户名靠前的户")
    total = "10.00"
    weights = {"alpha": 1, "beta": 1, "gamma": 1}
    allocation = allocate(total, list(weights.values()))
    print("  分摊 %s 给三个等权账户" % total)
    print("  各户份额: %s" % [format_cents(int(s * 100)) for s in allocation.shares])
    print("  份额合计: %s，待结算尾差: %s（记账时归 alpha）"
          % (format_cents(int(allocation.total_allocated() * 100)),
             format_cents(int(allocation.residual * 100))))
    ledger = Ledger()
    result = ledger.apply_batch("B-1", [BatchRequest(total, weights)])
    print("  记账后余额: %s" % {
        name: format_cents(int(value * 100))
        for name, value in sorted(result.balances.items())})
    print("  %s" % ledger.reconcile().render())


def reversal_batch():
    section("退款对冲批：零权重账户不动，尾差跟着总额走")
    ledger = Ledger()
    result = ledger.apply_batch("B-2", [
        BatchRequest("-10.00", {"coupon": 0, "alice": 1, "bob": 1, "carol": 1}),
    ])
    print("  冲抵 -10.00，权重: coupon=0 alice=1 bob=1 carol=1")
    for name in ["coupon", "alice", "bob", "carol"]:
        print("    %-7s credit=%s" % (
            name, format_cents(int(result.credits[name] * 100))))
    print("  %s" % ledger.reconcile().render())


def batch_drift():
    section("按批摊开：账面与请求总额始终对齐")
    ledger = Ledger()
    batches = 200
    for index in range(batches):
        ledger.apply_batch("B-%04d" % index, [
            BatchRequest("10.00", {"alpha": 1, "beta": 1, "gamma": 1}),
        ])
    expectation = batches * 10
    print("  %d 批，每批 10.00，请求总额 %s" % (
        batches, format_cents(expectation * 100)))
    print("  账面余额合计 %s" % format_cents(
        int(sum(ledger.balances().values(), from_cents(0)) * 100)))
    print("  %s" % ledger.reconcile().render())


def sub_cent_request():
    section("小于一分的请求")
    ledger = Ledger()
    print("  请求总额 0.004，权重 alpha=1 beta=1")
    try:
        ledger.apply_batch("B-3", [
            BatchRequest("0.004", {"alpha": 1, "beta": 1}),
        ])
    except MoneyError as exc:
        print("  被拒: %s" % exc)
    print("  账本余额: %s" % ledger.balances())
    print("  %s" % ledger.reconcile().render())


def replay_same_batch():
    section("同一批重放：返回首次结果，不重复入账")
    requests = [BatchRequest("6.00", {"alpha": 1, "beta": 1, "gamma": 1})]
    ledger = Ledger()
    first = ledger.apply_batch("B-4", requests)
    second = ledger.apply_batch("B-4", requests)
    print("  第一次余额: %s" % {
        name: format_cents(int(value * 100))
        for name, value in sorted(first.balances.items())})
    print("  重放后余额: %s" % {
        name: format_cents(int(value * 100))
        for name, value in sorted(second.balances.items())})
    print("  两次输出逐字节相同: %s" % (first.render() == second.render()))


def account_order_matters():
    section("同一笔请求，账户顺序不同，输出一致")
    total = "-10.00"
    first = Ledger().apply_batch("B-5", [
        BatchRequest(total, {"bob": 1, "carol": 1, "dave": 1}),
    ])
    second = Ledger().apply_batch("B-5", [
        BatchRequest(total, {"dave": 1, "carol": 1, "bob": 1}),
    ])
    print("  bob carol dave 顺序: %s" % {
        name: format_cents(int(value * 100))
        for name, value in first.credits.items()})
    print("  dave carol bob 顺序: %s" % {
        name: format_cents(int(value * 100))
        for name, value in second.credits.items()})
    print("  两份输出逐字节相同: %s" % (first.render() == second.render()))


def large_amount():
    section("大额入账：十几位金额一分不差")
    amount = "12345678901234567.89"
    expected_cents = 1234567890123456789
    ledger = Ledger()
    ledger.apply_batch("B-6", [BatchRequest(amount, {"alpha": 1, "beta": 2})])
    report = ledger.reconcile()
    print("  请求总额 %s 分，账上记的入账 %s 分"
          % (expected_cents, int(report.total_in * 100)))
    print("  差 %s" % format_cents(expected_cents - int(report.total_in * 100)))


def perf(requests=200000, accounts=5):
    section("压测 %d 笔请求 x %d 户" % (requests, accounts))
    rng = random.Random(20260920)
    names = ["acc%02d" % index for index in range(accounts)]
    ledger = Ledger()
    started = time.time()
    for index in range(requests):
        weights = {name: rng.randrange(0, 50) for name in names}
        if not any(weights.values()):
            weights[names[0]] = 1
        ledger.apply_batch("P-%06d" % index, [
            BatchRequest("%d.%02d" % (rng.randrange(0, 1000), rng.randrange(0, 100)),
                         weights),
        ])
    elapsed = time.time() - started
    shares = requests * accounts
    print("  份额 %d 个，耗时 %.1f 秒，%.0f 份额/秒"
          % (shares, elapsed, shares / elapsed))


def main():
    even_split_tail()
    print()
    reversal_batch()
    print()
    batch_drift()
    print()
    sub_cent_request()
    print()
    replay_same_batch()
    print()
    account_order_matters()
    print()
    large_amount()
    print()
    if len(sys.argv) > 1 and sys.argv[1] == "perf":
        perf()
    else:
        print("加参数 perf 可以跑大批量分摊的压测")


if __name__ == "__main__":
    main()
