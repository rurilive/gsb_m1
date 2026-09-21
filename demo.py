"""causalsnap 现状演示。

第一段：三个进程各记各的本地事件，共享单元读写。
第二段：预留的因果序与一致性快照样例位子（见文末注释）。
"""

from causalsnap.store import CausalStore


class TickClock:
    """每问一次涨 1 的假时钟，让演示输出可复现。"""

    def __init__(self):
        self._t = 0.0

    def __call__(self):
        self._t += 1.0
        return self._t


def main():
    print("=== 各进程本地事件与共享单元 ===")
    store = CausalStore(clock=TickClock())
    for payload in ("login", "edit"):
        store.record("alice", payload)
    for payload in ("join", "read"):
        store.record("bob", payload)
    store.record("carol", "audit")
    store.publish("alice", "doc", "draft")
    store.publish("bob", "doc", "final")

    for proc in store.processes():
        events = store.local(proc)
        print("  %s: %s" % (proc, [(e.seq, e.payload) for e in events]))
    print("  共享单元: %s -> doc=%r" % (store.cells(), store.fetch("doc")))

    # TODO(因果改造): 向量时钟与一致性快照实现后，在这里加一段演示：
    # 让 bob 收到 alice 的一条事件后各自再记事件，展示 compare 判出的
    # 先后与并发；再取两份快照，展示 cut 由哪些本地事件拼成、两份快照
    # 的新旧或并发，以及并发快照不许被硬排成先后。


if __name__ == "__main__":
    main()
