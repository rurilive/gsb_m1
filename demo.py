"""idemkit 现状演示。

第一段：注册处理器并提交执行几个任务。
第二段：幂等提交，展示同键重复提交复用首跑结果与重启重放。
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
    runs = []
    d2 = Dispatcher()
    d2.register("render", lambda p: runs.append(p) or render(p))
    store_dir = tempfile.mkdtemp(prefix="idemkit-demo-")
    sub = IdempotentSubmitter(d2, store_dir, ttl=3600)

    key = "cat.png#render"
    a = sub.submit(key, "render", {"name": "cat.png"})
    print(f"  首次提交   -> {a}")
    b = sub.submit(key, "render", {"name": "cat.png"})
    print(f"  重复提交   -> {b}（同键 TTL 内直接复用，handler 实跑 {len(runs)} 次）")

    # 模拟进程重启：新实例指向同一 store_dir，同键从落盘结果重放
    sub2 = IdempotentSubmitter(d2, store_dir, ttl=3600)
    c = sub2.submit(key, "render", {"name": "cat.png"})
    print(f"  重启重放   -> {c}（新实例同一目录，handler 仍只跑了 {len(runs)} 次）")


if __name__ == "__main__":
    main()
