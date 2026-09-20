"""healthd 现状演示。

第一段：注册几个探针，手动跑一轮检查并查看状态板。
第二段：常驻自检的位子（见文件末尾注释）。
"""

import random
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

    print("=== 常驻自检：超时降级与门限翻转 ===")
    flaky = {"ok": True}

    def check_flaky():
        if not flaky["ok"]:
            raise RuntimeError("flaky down")
        return "flaky up"

    def check_slow():
        time.sleep(0.5)  # 每次都超过自己的 timeout，判超时失败
        return "too late"

    runner2 = CheckRunner(k=2)  # 3 个探针里至少 2 个通过才可接流量
    runner2.register("db", check_db)
    runner2.register("slow", check_slow, timeout=0.1)
    runner2.register("flaky", check_flaky)
    runner2.on_change(lambda old, new: print(f"  [on_change] {old} -> {new}"))

    runner2.start(period=0.3, jitter=0.05)
    time.sleep(1.0)
    print(f"  slow 持续超时(2/3 通过): status={runner2.status()} ready={runner2.ready()}")

    flaky["ok"] = False
    time.sleep(1.0)
    print(f"  flaky 也挂了(1/3 < k=2): status={runner2.status()} ready={runner2.ready()}")

    flaky["ok"] = True
    time.sleep(1.0)
    print(f"  flaky 恢复(回到 2/3): status={runner2.status()} ready={runner2.ready()}")

    runner2.stop()


if __name__ == "__main__":
    main()
