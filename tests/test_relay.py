"""逐条投递通道的既有行为锁定。"""

import unittest

from cdcparse.events import data_line, ddl_line, txn_lines
from cdcparse.relay import StreamRelay
from cdcparse.sink import MemorySink
from cdcparse.stream import EventReader, MemorySource


def sample_log():
    """两个事务夹一条 DDL，位点 1 到 8 连号。"""
    first, pos = txn_lines(1, 11, [("insert", "orders", {"id": 1, "amount": 50}),
                                   ("update", "orders", {"id": 1, "amount": 80})])
    ddl = ddl_line(pos, "alter table orders add column note varchar(32)")
    second, _ = txn_lines(pos + 1, 12, [("delete", "orders", {"id": 2})])
    return first + [ddl] + second


def make_relay(lines):
    sink = MemorySink()
    relay = StreamRelay(EventReader(MemorySource(lines)), sink)
    return relay, sink


class StreamRelayTest(unittest.TestCase):
    def test_pump_delivers_data_and_ddl_immediately(self):
        relay, sink = make_relay(sample_log())
        pushed = relay.pump()
        self.assertEqual(pushed, 4)
        self.assertEqual(sink.pos_list(), [2, 3, 5, 7])

    def test_boundary_events_are_counted_not_delivered(self):
        relay, sink = make_relay(sample_log())
        relay.pump()
        self.assertEqual(relay.events_read, 8)
        self.assertEqual(relay.txns_opened, 2)
        self.assertEqual(relay.stats(), {"events_read": 8, "txns_opened": 2, "pushed": 4})

    def test_sink_gets_one_batch_per_change(self):
        relay, sink = make_relay(sample_log())
        relay.pump()
        self.assertEqual(sink.stats(), {"batches": 4, "changes": 4, "last_pos": 7})

    def test_pump_honours_max_events(self):
        relay, sink = make_relay(sample_log())
        self.assertEqual(relay.pump(max_events=4), 2)
        self.assertEqual(sink.pos_list(), [2, 3])
        self.assertEqual(relay.pump(), 2)
        self.assertEqual(sink.pos_list(), [2, 3, 5, 7])

    def test_pump_max_events_zero_reads_nothing(self):
        relay, sink = make_relay(sample_log())
        self.assertEqual(relay.pump(max_events=0), 0)
        self.assertEqual(relay.events_read, 0)

    def test_arrival_order_is_kept_even_when_positions_differ(self):
        lines = [data_line(3, 7, "insert", "t", {"id": 3}),
                 data_line(1, 7, "insert", "t", {"id": 1}),
                 data_line(2, 7, "insert", "t", {"id": 2})]
        relay, sink = make_relay(lines)
        relay.pump()
        self.assertEqual(sink.pos_list(), [3, 1, 2])
        self.assertEqual(sink.last_pos, 3)

    def test_pump_on_empty_log(self):
        relay, sink = make_relay([])
        self.assertEqual(relay.pump(), 0)
        self.assertEqual(sink.changes(), [])

    def test_change_payload_is_delivered_intact(self):
        log = sample_log()
        relay, sink = make_relay(log)
        relay.pump()
        first = sink.changes()[0]
        self.assertEqual(first["op"], "insert")
        self.assertEqual(first["table"], "orders")
        self.assertEqual(first["row"], {"id": 1, "amount": 50})
        self.assertEqual(first["xid"], 11)


if __name__ == "__main__":
    unittest.main()
