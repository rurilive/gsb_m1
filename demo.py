"""线程池现状演示。

第一段：submit / map / Task 句柄的基本用法。
第二段注释：优雅关闭实现后的演示位子。
"""

import time

from workerpool import WorkerPool


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

    # TODO(优雅关闭): close() 实现后，在这里补第二段演示：
    # 提交几个耗时任务再 close(grace_timeout=...)，打印关闭报告里
    # 完成与被取消的任务；顺带验证重复 close 幂等、
    # 关闭后 submit 抛 PoolClosed。

    print("\ndone.")


if __name__ == "__main__":
    main()
