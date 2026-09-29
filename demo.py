"""actorbox 现状演示。

第一段：用朴素同步 Registry 注册一个处理器，send 一步到位拿到返回值，
看它是怎么在调用方线程里被直接跑完的。
第二段：预留的 tell/ask 与监督演示位子（见文末注释）。
"""

from actorbox.registry import HandlerError, NoSuchActor, Registry


def main():
    print("=== 朴素同步分发（现有能力） ===")
    registry = Registry()
    seen = []

    def echo(message):
        seen.append(message)
        return "echo:" + message

    registry.register("echo", echo)
    print("  names        ->", registry.names())
    print("  send(hi)     ->", registry.send("echo", "hi"))
    print("  send(again)  ->", registry.send("echo", "again"))
    print("  处理器收到的 ->", seen)
    print("  处理器在调用方线程里同步跑完，send 返回即处理完毕")

    try:
        registry.send("missing", "hi")
    except NoSuchActor as exc:
        print("  投给不存在的目标 ->", type(exc).__name__)

    def boom(_message):
        raise ValueError("bad message")

    registry.register("boom", boom)
    try:
        registry.send("boom", "hi")
    except HandlerError as exc:
        print("  处理器抛异常     ->", type(exc).__name__, "cause:", type(exc.__cause__).__name__)

    # TODO(tell/ask 与监督): 异步邮箱、请求应答与监督就位后，在这里加一段演示：
    # 起一个有界邮箱的 actor，用 tell 投入若干消息并看到它们被顺序处理；
    # 再用 ask 发一条请求并拿到与它配对的应答，外加一次注入时钟下的超时；
    # 最后给一个会抛异常的子 actor 配上监督策略，展示重启或停止之后邮箱与行为的变化。


if __name__ == "__main__":
    main()
