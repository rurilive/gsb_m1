"""idemkit 现状演示。

第一段：注册处理器并提交执行几个任务。
第二段：幂等提交，重复提交拿同一结果，重启后从落盘结果重放。
"""

import tempfile

from idemkit import Dispatcher, IdempotentSubmitter


def render(payload):
    # 假装渲染了一张缩略图，返回产物信息
    return {"thumb": f"{payload['name']}_120.jpg", "bytes": 4821}


def watermark(payload):
    return {"marked": payload["name"], "at": "bottom-right"}


def main():
    d = Dispatcher()
    d.register("render", render)
    d.register("watermark", watermark)

    print("=== 同步提交执行 ===")
    r1 = d.dispatch("render", {"name": "cat.png"})
    print(f"  render(cat.png)    -> {r1}")
    r2 = d.dispatch("watermark", {"name": "cat.png"})
    print(f"  watermark(cat.png) -> {r2}")
    print("  （上游是至少一次投递，同一个任务被重复提交时现在每次都会真跑一遍）")

    print("=== 幂等提交 ===")
    store_dir = tempfile.mkdtemp(prefix="idemkit-store-")
    runs = []

    def counted_render(payload):
        runs.append(payload)
        return render(payload)

    d2 = Dispatcher()
    d2.register("render", counted_render)
    sub = IdempotentSubmitter(d2, store_dir, ttl=3600)

    key = "render:cat.png:2026-09-19"
    r1 = sub.submit(key, "render", {"name": "cat.png"})
    r2 = sub.submit(key, "render", {"name": "cat.png"})
    print(f"  首次提交   -> {r1}")
    print(f"  重复提交   -> {r2}（同一结果，handler 累计执行 {len(runs)} 次）")

    sub2 = IdempotentSubmitter(d2, store_dir, ttl=3600)  # 模拟进程重启：新实例指同一目录
    r3 = sub2.submit(key, "render", {"name": "cat.png"})
    print(f"  重启后重放 -> {r3}（从落盘结果重放，handler 仍只执行 {len(runs)} 次）")


if __name__ == "__main__":
    main()
