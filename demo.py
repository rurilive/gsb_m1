"""线程池演示：submit / map / Task 句柄与优雅关闭。"""

import time

from workerpool import PoolClosed, WorkerPool


def fetch(item):
    # 模拟一次带耗时的外部调用
    time.sleep(0.05)
    return f"resp-{item}"


def main():
    print("=== submit / Task 句柄 ===")
    pool = WorkerPool(3)
    tasks = [pool.submit(fetch, i) for i in range(3)]
    for t in tasks:
        print(f"  result={t.result(5)} state={t.state}")

    print("\n=== map 批量转换 ===")
    squares = pool.map(lambda x: x * x, range(1, 8))
    print(f"  squares = {squares}")

    print("\n=== 任务异常不拖垮工作线程 ===")
    bad = pool.submit(int, "not-a-number")
    try:
        bad.result(5)
    except ValueError as exc:
        print(f"  caught from task: {exc}")
    good = pool.submit(fetch, 7)
    print(f"  next task on same pool: {good.result(5)}")

    print("\n=== 优雅关闭 close(grace_timeout) ===")
    shutdown_pool = WorkerPool(2)
    print(f"  atexit_registered = {shutdown_pool.atexit_registered}")
    # 3 个快任务 + 2 个慢任务；池只有 2 个槽，慢任务占住后其余排队
    quick = [shutdown_pool.submit(fetch, i) for i in range(3)]
    slow = [shutdown_pool.submit(time.sleep, 0.5) for _ in range(2)]
    report = shutdown_pool.close(grace_timeout=0.2)
    print(f"  close 报告: completed={report.completed} "
          f"cancelled={len(report.cancelled)}")
    for t in quick:
        print(f"  quick #{t.seq}: {t.state} -> {t.result(5)!r}")
    for t in slow:
        print(f"  slow  #{t.seq}: {t.state}")

    # 重复 close 幂等：返回同一份首次报告
    print(f"  再次 close 返回同一报告: {shutdown_pool.close() is report}")
    # 关闭后拒收新任务
    try:
        shutdown_pool.submit(fetch, 99)
    except PoolClosed as exc:
        print(f"  关闭后 submit: {type(exc).__name__}: {exc}")

    print("\ndone.")


if __name__ == "__main__":
    main()
