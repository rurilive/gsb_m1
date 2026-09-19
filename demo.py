"""idemkit 现状演示。

第一段：注册处理器并提交执行几个任务。
第二段：幂等提交的位子（见文件末尾注释）。
"""

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

    # TODO(幂等改造): 幂等键层实现后，在这里用同一个 idem_key 重复提交
    # 同一任务，展示第二次直接拿到首跑结果、handler 不再执行，
    # 再演示重启进程后同键从落盘结果重放。


if __name__ == "__main__":
    main()
