"""healthd 现状演示。

第一段：注册几个探针，手动跑一轮检查并查看状态板。
第二段：常驻自检的位子（见文件末尾注释）。
"""

import random

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

    # TODO(常驻自检): 自检线程实现后，在这里注册探针超时与就绪门限，
    # 起后台线程跑几轮，展示探针超时降级、恢复翻转和 ready 门限的效果。


if __name__ == "__main__":
    main()
