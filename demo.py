"""handshake 演示：转移表驱动的会话状态机。

第一段：strong 套件握手到 FULL 稳态。
第二段：weak 套件握手到 DEGRADED 稳态。
第三段：hello 阶段超时回 CLOSED。
第四段：FULL 稳态触发 rekey，三步协商成功回 FULL。
第五段：DEGRADED 稳态 rekey 一步超时回退，会话仍可用，再次 rekey 成功。
"""

from handshake import Ev, REKEY_TIMEOUT, Session


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
    clock.advance(1.0)

    s4 = Session(clock=clock)
    s4.feed(Ev.START)
    s4.feed(Ev.PEER_HELLO, "strong")
    s4.feed(Ev.PEER_KEY)
    s4.feed(Ev.PEER_AUTH_OK)
    s4.feed(Ev.REKEY)
    s4.feed(Ev.PEER_REKEY_ACCEPT)
    s4.feed(Ev.PEER_REKEY_DONE)
    show("FULL 上 rekey 三步成功 -> FULL", s4)
    clock.advance(1.0)

    s5 = Session(clock=clock)
    s5.feed(Ev.START)
    s5.feed(Ev.PEER_HELLO, "weak")
    s5.feed(Ev.PEER_KEY)
    s5.feed(Ev.PEER_AUTH_OK)
    s5.feed(Ev.REKEY)
    clock.advance(REKEY_TIMEOUT)
    s5.poll()
    print("--- DEGRADED 上 rekey 超时回退 ---")
    print(f"state={s5.state.value}（连接不断）")
    s5.feed(Ev.REKEY)
    s5.feed(Ev.PEER_REKEY_ACCEPT)
    s5.feed(Ev.PEER_REKEY_DONE)
    print(f"再次 rekey 成功: state={s5.state.value}")
    for e in s5.log[-10:]:
        print(f"  [{e.ts:>5.1f}] {e.kind:<8}{e.detail}")
    print()


if __name__ == "__main__":
    main()
