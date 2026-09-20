"""handshake 演示：转移表驱动的会话状态机。

第一段：strong 套件握手到 FULL 稳态。
第二段：weak 套件握手到 DEGRADED 稳态。
第三段：hello 阶段超时回 CLOSED。
"""

from handshake import Ev, Session


class FakeClock:
    """演示用注入时钟。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def show(title, session):
    print(f"--- {title} ---")
    print(f"state={session.state.value} suite={session.suite}")
    for e in session.log:
        print(f"  [{e.ts:>5.1f}] {e.kind:<8}{e.detail}")
    print()


def main():
    clock = FakeClock()

    s1 = Session(clock=clock)
    s1.feed(Ev.START)
    s1.feed(Ev.PEER_HELLO, "strong")
    s1.feed(Ev.PEER_KEY)
    s1.feed(Ev.PEER_AUTH_OK)
    show("strong 套件握手 -> FULL", s1)
    clock.advance(1.0)

    s2 = Session(clock=clock)
    s2.feed(Ev.START)
    s2.feed(Ev.PEER_HELLO, "weak")
    s2.feed(Ev.PEER_KEY)
    s2.feed(Ev.PEER_AUTH_OK)
    show("weak 套件握手 -> DEGRADED", s2)
    clock.advance(1.0)

    s3 = Session(clock=clock)
    s3.feed(Ev.START)
    clock.advance(3.0)
    s3.poll()
    show("hello 阶段超时 -> CLOSED", s3)

    # TODO(rekey): rekey 子流程就位后，在这里加两个演示：
    # 1) 稳态触发 rekey，三步协商成功回到原稳态
    # 2) rekey 一步超时回退，会话仍然可用


if __name__ == "__main__":
    main()
