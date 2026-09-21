"""发放、续期、归还的连环吞吐基准。

一轮是 grant 加 renew 加 release 三次调用，threads 个线程各守一个资源
连环跑 seconds 秒，量每秒完成的调用数，多轮取最好抹调度噪声。
candidates 登记进比对的实现，以后新实现加一行就能进表。
"""

import threading
import time

from leasekeeper.clock import FakeClock
from leasekeeper.durable import DurableLeaseKeeper
from leasekeeper.journal import MemoryJournal
from leasekeeper.keeper import LeaseKeeper

DEFAULT_THREADS = (1, 2, 4)
DEFAULT_SECONDS = 0.5
DEFAULT_TRIALS = 2


def _run_once(make_keeper, threads, seconds, sleep):
    keeper = make_keeper()
    stop = threading.Event()
    counts = [0] * threads

    def work(index):
        done = 0
        resource = "bench.res-%d" % index
        who = "bench-w%d" % index
        grant = keeper.grant
        renew = keeper.renew
        release = keeper.release
        while not stop.is_set():
            lease = grant(resource, who, 60.0)
            renew(lease.lease_id, who)
            release(lease.lease_id, who)
            done += 3
        counts[index] = done

    workers = [threading.Thread(target=work, args=(i,)) for i in range(threads)]
    started = time.perf_counter()
    for worker in workers:
        worker.start()
    sleep(seconds)
    stop.set()
    for worker in workers:
        worker.join()
    elapsed = time.perf_counter() - started
    return sum(counts) / elapsed


def measure(make_keeper, threads=2, seconds=DEFAULT_SECONDS,
            trials=DEFAULT_TRIALS, sleep=time.sleep):
    """量 threads 个线程连环跑 grant+renew+release 的吞吐，返回每秒调用数。"""
    return max(
        _run_once(make_keeper, threads, seconds, sleep)
        for _ in range(trials)
    )


def candidates():
    """进比对的实现列表：(名字, 建发放台的可调用对象)。"""
    return [
        ("naive", LeaseKeeper),
        ("durable", lambda: DurableLeaseKeeper(journal=MemoryJournal())),
    ]


def sweep_cost(factory, active=20000, dead=20):
    """造 active 份活跃租约、其中 dead 份到期，量一次 sweep 的秒数。

    dead 份短租期先到，其余 active-dead 份长租期还活着；用注入假钟
    把时刻拨到短租约全过期、长租约都没过期。返回 (耗时, 清掉条数)。
    """
    clock = FakeClock()
    keeper = factory(clock.current)
    for index in range(dead):
        keeper.grant("res-dead-%05d" % index, "n", 5.0)
    for index in range(active - dead):
        keeper.grant("res-alive-%05d" % index, "n", 3600.0)
    clock.advance(6.0)
    started = time.perf_counter()
    expired = keeper.sweep()
    elapsed = time.perf_counter() - started
    return elapsed, len(expired)


def compare_sweep(active=20000, dead=20):
    """全表扫的内存版与按到期槽的日志版，巡检两万活跃/少量到期的耗时。"""
    rows = []

    def make_naive(clock):
        return LeaseKeeper(clock=clock)

    def make_durable(clock):
        return DurableLeaseKeeper(clock=clock, journal=MemoryJournal())

    for name, factory in (("naive", make_naive), ("durable", make_durable)):
        elapsed, removed = sweep_cost(factory, active=active, dead=dead)
        rows.append((name, elapsed, removed))
    return rows


def main(threads=DEFAULT_THREADS, seconds=DEFAULT_SECONDS,
         trials=DEFAULT_TRIALS):
    print("grant+renew+release 连环吞吐，%g 秒一轮、%d 轮取最好" % (seconds, trials))
    print("%-10s" % "实现" + "".join("%12s" % ("%d 线程" % t) for t in threads))
    for name, make_keeper in candidates():
        cells = [
            measure(make_keeper, t, seconds=seconds, trials=trials)
            for t in threads
        ]
        print("%-10s" % name + "".join("%12.0f" % c for c in cells))
    print()
    print("两万活跃租约、当轮 20 条到期时的 sweep 耗时：")
    for name, elapsed, removed in compare_sweep():
        print("  %-8s %.6f 秒（清掉 %d 条）" % (name, elapsed, removed))


if __name__ == "__main__":
    main()
