"""stealpool 现状演示：提交取结果、任务树对拍、取消一个还没开跑的任务。"""

import threading
import time

from stealpool import Pool, TaskCancelled
from stealpool.reference import TaskNode, TreeRunner, run_sequential


def fetch(name, delay=0.02):
    time.sleep(delay)
    return "body:" + name


def main():
    print("=== 提交与取结果（3 个 worker） ===")
    pool = Pool(3)
    futures = [pool.submit(fetch, "page%d" % i) for i in range(6)]
    print("  结果:", [f.result() for f in futures])
    pool.shutdown()
    snap = pool.stats()
    print("  submitted=%d completed=%d failed=%d steals=%d"
          % (snap["submitted"], snap["completed"], snap["failed"], snap["steals"]))
    print("  每 worker 忙碌秒数:", ["%.3f" % s for s in snap["busy_seconds"]])
    print("  每 worker 空闲秒数:", ["%.3f" % s for s in snap["idle_seconds"]])

    print("=== 任务树：顺序参考对拍并行执行 ===")
    tree = TaskNode(
        "page",
        (
            TaskNode("links", work=0.03, tag=2),
            TaskNode("images", (TaskNode("thumb", work=0.03, tag=3),), work=0.02, tag=5),
        ),
        work=0.02,
        tag=100,
    )
    started = time.monotonic()
    expected = run_sequential(tree)
    sequential_seconds = time.monotonic() - started
    with Pool(4) as tree_pool:
        started = time.monotonic()
        got = TreeRunner(tree_pool).run(tree)
        parallel_seconds = time.monotonic() - started
    print("  顺序结果:", expected)
    print("  并行结果:", got, "一致" if got == expected else "不一致")
    print("  顺序 %.3fs，并行 %.3fs" % (sequential_seconds, parallel_seconds))

    print("=== 取消一个还没开跑的任务 ===")
    pool = Pool(2)
    release = threading.Event()
    blockers = [pool.submit(release.wait, 5.0) for _ in range(2)]
    victim = pool.submit(fetch, "cancel-me")
    print("  cancel 返回:", victim.cancel())
    try:
        victim.result()
    except TaskCancelled as exc:
        print("  取结果抛出:", type(exc).__name__, exc)
    release.set()
    for blocker in blockers:
        blocker.result(5.0)
    pool.shutdown()

    # TODO(工作窃取改造): 换成窃取版调度后，在这里补一段演示：不匀称的
    # 任务树上各 worker 的分工、单 worker 跑深链、取消整条链时没开跑的
    # 子任务不执行，以及 stats 里的偷取计数。


if __name__ == "__main__":
    main()
