"""causalsnap 现状演示。

第一段：三个进程各记各的本地事件，共享单元读写。
第二段：向量时钟判因果，一致性快照比新旧。
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

    print("=== 因果序与一致性快照 ===")
    # bob 收到 alice 的第 1 条事件（edit），随后各自再记新事件
    store.observe("bob", "alice", 1)
    store.record("bob", "reply")
    store.record("alice", "publish")
    store.record("carol", "comment")

    alice_edit = store.local("alice")[1]
    alice_publish = store.last("alice")
    bob_reply = store.last("bob")
    carol_comment = store.last("carol")
    print("  bob 的 reply 见过 alice 的 edit: compare = %s" % store.compare(bob_reply, alice_edit))
    print("  alice 的 publish 与 bob 的 reply 互不知情: compare = %s" % store.compare(alice_publish, bob_reply))
    print("  carol 的 comment 与两者皆并发: %s / %s" % (
        store.compare(carol_comment, bob_reply), store.compare(carol_comment, alice_publish)))

    snap_before = store.snapshot("bob")
    store.observe("bob", "alice", 2)  # bob 又收到 alice 的 publish
    snap_after = store.snapshot("bob")
    snap_carol = store.snapshot("carol")
    for snap in (snap_after, snap_carol):
        print("  %s 的快照 cut=%s" % (snap.observer, snap.cut))
        for proc, events in snap.events.items():
            print("    %s: %s" % (proc, [(e.seq, e.payload) for e in events]))
    print("  同一观察者先后两快照: compare = %s" % snap_after.compare(snap_before))
    print("  bob 与 carol 各看见各的: compare = %s（并发，不硬排）" % snap_after.compare(snap_carol))


if __name__ == "__main__":
    main()
