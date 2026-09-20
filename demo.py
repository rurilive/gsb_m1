"""healthd 演示。

第一段：注册几个探针，手动跑一轮检查并查看状态板。
第二段：常驻自检线程，展示探针超时降级、恢复翻转和 ready 门限。
"""

import random
import threading
import time

from healthd import CheckRunner


def check_db():
    # 假装探一下主库连通性
    return "primary up"


def check_queue():
    # 模拟队列积压探针：积压过深直接抛错
    depth = random.randrange(0, 60)
    if depth > 45:
        raise RuntimeError(f"backlog={depth}")
    return f"depth={depth}"


def check_disk():
    return "72% used"


def main():
    runner = CheckRunner()
    runner.register("db", check_db)
    runner.register("queue", check_queue)
    runner.register("disk", check_disk)

    print("=== 手动跑一轮检查 ===")
    snap = runner.run_once()
    for name in runner.names():
        r = snap[name]
        mark = "PASS" if r.ok else "FAIL"
        print(f"  [{mark}] {name:<6} {r.detail}")
    print(f"  overall_ok = {runner.board.overall_ok()}")

    demo_resident()


def demo_resident():
    """常驻自检：3 个探针，门限 k=2（至少 2 个通过才接流量）。
    queue 探针带 0.3s 超时，用来复现「探针卡死不再拖死整轮」；
    db 探针靠开关制造故障，演示 k/n 门限翻转与健康/就绪两回事。
    """
    print("=== 常驻自检：超时降级 + k/n 门限翻转（k=2, n=3）===")
    block_queue = threading.Event()    # 置位后 queue 探针每轮都卡死
    release_queue = threading.Event()  # 放行所有卡死的 queue 线程
    db_down = threading.Event()       # 置位后 db 探针失败

    def check_db_resident():
        if db_down.is_set():
            raise RuntimeError("conn refused")
        return "primary up"

    def check_queue_resident():
        if block_queue.is_set():
            # 等放行信号或故障解除（真实 hang 住的队列探针就是不返回）
            release_queue.wait(5)
            if block_queue.is_set():
                release_queue.clear()
        return "depth ok"

    runner = CheckRunner(period=0.5, jitter=0.1, k=2)
    runner.register("db", check_db_resident)
    runner.register("disk", check_disk)
    # queue 注册在最后：它卡死超时不拖累前面探针的执行节奏
    runner.register("queue", check_queue_resident, timeout=0.3)

    def on_change(old, new):
        print(f"  >> 状态翻转: {old} -> {new}")

    runner.on_change(on_change)

    def show(tag):
        print(f"  [{tag}] status={runner.status():<8} ready={runner.ready()}")

    runner.start()
    time.sleep(0.2)
    show("起步全部通过")

    # 1) queue 卡死：超时判失败，但 db+disk 仍 2/3 达门限 -> degraded 且仍接流量
    block_queue.set()
    time.sleep(1.3)
    show("queue 卡死超时")

    # 2) db 再挂：只剩 1/3，低于门限 -> down，摘流量
    db_down.set()
    time.sleep(1.3)
    show("db 也挂了")

    # 3) db 恢复、queue 仍卡：2/3 -> degraded，重新接流量
    db_down.clear()
    time.sleep(1.3)
    show("db 恢复，queue 仍卡")

    # 4) 放行 queue：后续轮次早已重新探通，db 一恢复即回到 3/3 -> ok
    block_queue.clear()
    release_queue.set()
    time.sleep(1.3)
    show("queue 恢复")

    runner.stop()


if __name__ == "__main__":
    main()
