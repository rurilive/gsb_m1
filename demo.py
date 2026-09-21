"""centledger 现状演示：把线上反馈的几类现象直接跑出来。

一笔十块钱均摊到三个账户，尾差没人管；退款对冲批里零权重账户被扣钱；
分批跑得越多账面跟请求总额差得越远；比一分小的请求无声无息；
同一批重放余额翻倍；大额入账差几分。修好之后，各段输出应该
与财务口径一致，重放输出稳定。
"""

import random
import sys
import time

from centledger import BatchRequest, Ledger, allocate, format_cents, from_cents


def section(title):
    print("=== %s ===" % title)


def even_split_tail():
    section("均摊的尾差没人管")
    total = "10.00"
    weights = {"alpha": 1, "beta": 1, "gamma": 1}
    allocation = allocate(total, list(weights.values()))
    print("  分摊 %s 给三个等权账户" % total)
    print("  各户份额: %s" % [format_cents(int(s * 100)) for s in allocation.shares])
    print("  份额合计: %s，未摊出的尾差: %s"
          % (format_cents(int(allocation.total_allocated() * 100)),
             format_cents(int(allocation.residual * 100))))
    ledger = Ledger()
    result = ledger.apply_batch("B-1", [BatchRequest(total, weights)])
    print("  记账后余额: %s" % {
        name: format_cents(int(value * 100))
        for name, value in sorted(result.balances.items())})
    print("  %s" % ledger.reconcile().render())


def reversal_batch():
    section("退款对冲批：零权重账户被扣尾差")
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
    section("按批摊开后累计漂移")
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
    result = ledger.apply_batch("B-3", [
        BatchRequest("0.004", {"alpha": 1, "beta": 1}),
    ])
    print("  请求总额 0.004，权重 alpha=1 beta=1")
    print("  批次结果里的账户: %s" % sorted(result.credits))
    print("  账本余额: %s" % ledger.balances())
    print("  %s" % ledger.reconcile().render())


def replay_same_batch():
    section("同一批重放")
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
    section("同一笔请求，账户顺序不同")
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
    section("大额入账")
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
