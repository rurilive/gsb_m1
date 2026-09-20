"""idemkit 现状演示。

第一段：注册处理器并提交执行几个任务。
第二段：幂等提交演示——同键重复提交只跑一次，重启后同键从落盘结果重放。
"""

import tempfile

from idemkit.idempotent import IdempotentSubmitter
from idemkit import Dispatcher


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
    print("=== 幂等提交 ===")
    store_dir = tempfile.mkdtemp(prefix="idemkit-demo-")
    s = IdempotentSubmitter(d, store_dir, ttl=24 * 3600)

    key = "render:cat.png:2026-09-20"
    first = s.submit(key, "render", {"name": "cat.png"})
    # 网络抖动，上游用同一个键重发两次（payload 不同也不会重跑）
    retry1 = s.submit(key, "render", {"name": "cat.png"})
    retry2 = s.submit(key, "render", {"name": "cat.png-DUP"})
    print(f"  首跑          -> {first}")
    print(f"  重复提交第 1 次 -> {retry1}")
    print(f"  重复提交第 2 次 -> {retry2}")
    print(f"  三次提交结果相同: {first == retry1 == retry2}")
    print("  render handler 全程只执行了一次，重复提交直接回放首跑结果")

    # 模拟进程重启：新建 submitter（甚至新建 Dispatcher）指向同一目录
    d2 = Dispatcher()
    d2.register("render", render)
    d2.register("watermark", watermark)
    s2 = IdempotentSubmitter(d2, store_dir, ttl=24 * 3600)
    replayed = s2.submit(key, "render", {"name": "cat.png"})
    print(f"  重启后同键提交 -> {replayed}")
    print(f"  重启重放结果一致: {replayed == first}")
    print(f"  落盘目录: {store_dir}")


if __name__ == "__main__":
    main()
