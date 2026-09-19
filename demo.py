"""idemkit 现状演示。

第一段：注册处理器并提交执行几个任务。
第二段：幂等提交：同键重复提交拿同一结果，重启后从磁盘重放。
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

    print()
    print("=== 幂等提交（同键 TTL 内只跑一次）===")
    store_dir = tempfile.mkdtemp(prefix="idemkit-demo-")
    counter = {"render": 0}

    def render_once(payload):
        counter["render"] += 1
        return render(payload)

    d2 = Dispatcher()
    d2.register("render", render_once)
    submitter = IdempotentSubmitter(d2, store_dir, ttl=3600)

    key = "order-20260920-0001"
    a = submitter.submit(key, "render", {"name": "dog.png"})
    b = submitter.submit(key, "render", {"name": "dog.png"})
    print(f"  第一次提交        -> {a}")
    print(f"  同键重复提交      -> {b}")
    print(f"  两次结果相同: {a == b}，handler 实际执行 {counter['render']} 次")

    print()
    print("=== 重启重放（新实例指向同一目录）===")
    d3 = Dispatcher()
    d3.register("render", render_once)
    restarted = IdempotentSubmitter(d3, store_dir, ttl=3600)
    c = restarted.submit(key, "render", {"name": "dog.png"})
    print(f"  重启后同键提交    -> {c}")
    print(f"  handler 仍只执行 {counter['render']} 次，结果由磁盘文件重放: {store_dir}")


if __name__ == "__main__":
    main()
