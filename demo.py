"""cdcparse 现状演示。

第一段：一条一条读事件流，看位点与类型。
第二段：用逐条投递通道把变更推给下游。
第三段：留给成组交付与续跑演示的位子（见文末注释）。
"""

from cdcparse.events import ddl_line, txn_lines
from cdcparse.relay import StreamRelay
from cdcparse.sink import MemorySink
from cdcparse.stream import EventReader, MemorySource


def sample_log():
    first, pos = txn_lines(101, 5501, [("insert", "orders", {"id": 1, "amount": 50}),
                                       ("update", "orders", {"id": 1, "amount": 80})])
    ddl = ddl_line(pos, "alter table orders add column note varchar(32)")
    second, _ = txn_lines(pos + 1, 5502, [("delete", "orders", {"id": 1})])
    return first + [ddl] + second


def main():
    log = sample_log()

    print("=== 逐条读取 ===")
    reader = EventReader(MemorySource(log))
    while True:
        event = reader.read_event()
        if event is None:
            break
        extra = event.table or event.sql or ""
        print("  pos=%-3d %-6s %s" % (event.pos, event.kind, extra))
    print("  读到 %d 行，最后位点 %d" % (reader.arrivals, reader.position))

    print("=== 逐条投递（现状） ===")
    sink = MemorySink()
    relay = StreamRelay(EventReader(MemorySource(log)), sink)
    pushed = relay.pump()
    for change in sink.changes():
        print("  pos=%-3d %s %s xid=%s" % (change["pos"], change["op"],
                                           change["table"], change["xid"]))
    print("  投出 %d 条，下游累计 %s" % (pushed, sink.stats()))

    # TODO(成组交付): TxDeliverer 落地后，在这里补第三段演示：
    # 同一份日志按事务边界成组交给下游，DDL 默认被挡下；
    # 再把同一批位点重投一遍看下游不涨，以及带着 checkpoint 续跑。


if __name__ == "__main__":
    main()
