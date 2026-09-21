"""spanweave 现状演示：把四类重建问题直接跑出来。

依次演示同一毫秒的兄弟顺序跟着到达顺序漂移、子 span 先到就被丢掉、
跨进程上报丢了 parent_id 的根被塞进别的链路、时钟回拨采出负耗时。
修好之后这些输出会恢复正常。
"""

from spanweave import SpanStore, build, critical_path, render_tree, snapshot, summary

ROOT = {
    "trace_id": "tr-1", "span_id": "root", "parent_id": None,
    "name": "handle", "service": "api", "start_ms": 0, "end_ms": 100,
}


def child(span_id, start_ms, end_ms, service="svc"):
    return {
        "trace_id": "tr-1", "span_id": span_id, "parent_id": "root",
        "name": span_id, "service": service,
        "start_ms": start_ms, "end_ms": end_ms,
    }


def _indent(text):
    return text.replace("\n", "\n    ")


def same_tick():
    print("=== 同一毫秒的兄弟，顺序跟着到达顺序漂移 ===")
    one = build([ROOT, child("span-b", 1000, 1005), child("span-a", 1000, 1005)])[0]
    two = build([ROOT, child("span-a", 1000, 1005), child("span-b", 1000, 1005)])[0]
    print("  先到 b 后到 a 的重建结果:")
    print("    " + _indent(render_tree(one)))
    print("  先到 a 后到 b 的重建结果:")
    print("    " + _indent(render_tree(two)))
    print("  两次 snapshot 相同: %s（期望 True）"
          % (snapshot(one) == snapshot(two)))


def late_child():
    print("=== 子 span 先到、父 span 后到 ===")
    store = SpanStore()
    store.feed([child("s-child", 1000, 1010)])   # 子先上报
    store.feed([ROOT])                           # 父下一批才到
    tree = store.traces()[0]
    print("  重建结果:")
    print("    " + _indent(render_tree(tree)))
    print("  summary: %s" % summary(tree))


def cross_process():
    print("=== 跨进程上报丢了 parent_id 的根 ===")
    record = [ROOT, child("s-child", 1000, 1010), {
        "trace_id": "tr-1", "span_id": "s-foreign", "name": "injected",
        "service": "worker", "start_ms": 1200, "end_ms": 1250,
    }]
    tree = build(record)[0]
    print("  重建结果:")
    print("    " + _indent(render_tree(tree)))
    print("  summary: %s（roots 期望 2）" % summary(tree))


def clock_rollback():
    print("=== 时钟回拨采出负耗时 ===")
    records = [
        ROOT,
        child("s-a", 20, 70),
        {"trace_id": "tr-1", "span_id": "s-b", "parent_id": "s-a",
         "name": "s-b", "service": "cron", "start_ms": 80, "end_ms": 0},
        {"trace_id": "tr-1", "span_id": "s-c", "parent_id": "s-b",
         "name": "s-c", "service": "cron", "start_ms": 90, "end_ms": 120},
    ]
    tree = build(records)[0]
    print("  重建结果:")
    print("    " + _indent(render_tree(tree)))
    print("  summary: %s" % summary(tree))
    print("  critical_path: %s（期望 ['root', 's-a', 's-b', 's-c']）"
          % critical_path(tree))


def main():
    same_tick()
    print()
    late_child()
    print()
    cross_process()
    print()
    clock_rollback()


if __name__ == "__main__":
    main()
