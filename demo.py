"""spillkit 现状演示：把溢写路径上出问题的几类现象直接跑出来。

数据装得进内存时结果都对；一旦触发落盘，就会出现重复行、尾部丢失、
溢写文件一多句柄直接爆掉。最后拿随机数据跟朴素实现对比。
修好之后，各段的输出应该与朴素实现完全一致。
"""

import random
import sys
import time

from spillkit import SortDeduper, TooManyOpenRuns, sort_dedup


def naive(records, key):
    """朴素参考实现：稳定排序，同一个 key 只留最先出现的那条。"""
    ordered = sorted(records, key=key)
    out = []
    last = object()
    for record in ordered:
        record_key = key(record)
        if record_key == last:
            continue
        out.append(record)
        last = record_key
    return out


def default_key(record):
    return record.split("\t", 1)[0]


def section(title):
    print("=== %s ===" % title)


def duplicates_across_runs():
    section("重复记录被拆到不同溢写文件")
    first = ["k2\tA", "k1\tB", "k2\tC", "k3\tD"]
    second = ["k1\tE", "k4\tF", "k3\tG", "k1\tH"]
    records = first + second
    out = sort_dedup(records, memory_limit=4)
    expected = naive(records, default_key)
    print("  输入 8 条，内存上限 4 条")
    print("  溢写结果: %s" % out)
    print("  朴素结果: %s" % expected)
    print("  两条 k1 都在: %s" % ("k1\tE" in out and "k1\tB" in out))


def tail_buffer_dropped():
    section("收尾时没写满的缓冲被漏掉")
    records = ["k%02d\tv" % i for i in range(13)]
    out = sort_dedup(records, memory_limit=5)
    expected = naive(records, default_key)
    print("  输入 13 条，内存上限 5 条")
    print("  溢写结果 %d 条，朴素结果 %d 条" % (len(out), len(expected)))
    missing = [r for r in expected if r not in out]
    print("  丢失的记录: %s" % missing)


def too_many_open_runs():
    section("溢写文件数超过句柄上限")
    records = ["k%03d\tv" % i for i in range(40)]
    sorter = SortDeduper(memory_limit=2, fd_limit=4)
    try:
        for record in records:
            sorter.add(record)
        try:
            sorter.finish()
            print("  归并成功，未报句柄错误")
        except TooManyOpenRuns as exc:
            print("  归并报错: %s" % exc)
    finally:
        sorter.close()


def random_comparison():
    section("随机数据跟朴素实现对拍")
    rng = random.Random(20260920)
    keys = ["k%03d" % i for i in range(120)]
    records = [
        "%s\t%d" % (rng.choice(keys), i) for i in range(1500)
    ]
    out = sort_dedup(records, memory_limit=64, fd_limit=64)
    expected = naive(records, default_key)
    same = out == expected
    print("  1500 条随机记录，内存上限 64 条")
    print("  与朴素实现一致: %s" % same)
    if not same:
        for i, (got, want) in enumerate(zip(out, expected)):
            if got != want:
                print("  首个差异 @%d: 溢写 %r，朴素 %r" % (i, got, want))
                break
        print("  长度: 溢写 %d，朴素 %d" % (len(out), len(expected)))


def perf(count=1000000):
    section("压测 %d 条" % count)
    rng = random.Random(7)
    keys = ["k%06d" % rng.randrange(200000) for _ in range(count)]
    sorter = SortDeduper(memory_limit=50000, fd_limit=8)
    started = time.time()
    try:
        for i in range(count):
            sorter.add("%s\t%d" % (keys[i], i))
        try:
            out = sorter.finish()
        except TooManyOpenRuns as exc:
            print("  归并报错: %s" % exc)
            return
        elapsed = time.time() - started
        print("  输入 %d 条，输出 %d 条" % (count, len(out)))
        print("  耗时 %.1f 秒，run 文件 %d 个，归并 %d 趟"
              % (elapsed, sorter.stats()["runs_written"],
                 sorter.stats()["merge_passes"]))
    finally:
        sorter.close()


def main():
    duplicates_across_runs()
    print()
    tail_buffer_dropped()
    print()
    too_many_open_runs()
    print()
    random_comparison()
    if len(sys.argv) > 1 and sys.argv[1] == "perf":
        print()
        perf()
    else:
        print()
        print("加参数 perf 可以跑一百万条的压测")


if __name__ == "__main__":
    main()
