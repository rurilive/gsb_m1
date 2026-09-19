"""idemkit 现状演示。

第一段：注册处理器并提交执行几个任务。
第二段：幂等提交的位子（见文件末尾注释）。
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
    store_dir = tempfile.mkdtemp(prefix="idemkit-demo-")
    runs = {"render": 0}

    def counted_render(payload):
        runs["render"] += 1
        return render(payload)

    d2 = Dispatcher()
    d2.register("render", counted_render)
    sub = IdempotentSubmitter(d2, store_dir, ttl=3600)
    key = "thumb-cat.png-001"
    r3 = sub.submit(key, "render", {"name": "cat.png"})
    print(f"  首跑            -> {r3}")
    r4 = sub.submit(key, "render", {"name": "cat.png"})
    print(f"  同键重复提交    -> {r4}（handler 实际执行 {runs['render']} 次）")

    print("=== 重启重放 ===")
    runs["render"] = 0
    d3 = Dispatcher()  # 模拟进程重启：新 Dispatcher、新 Submitter，同一 store_dir
    d3.register("render", counted_render)
    sub2 = IdempotentSubmitter(d3, store_dir, ttl=3600)
    r5 = sub2.submit(key, "render", {"name": "cat.png"})
    print(f"  重启后同键提交  -> {r5}（handler 实际执行 {runs['render']} 次，结果来自落盘文件）")


if __name__ == "__main__":
    main()
