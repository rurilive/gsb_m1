"""来源与逐条读取器的既有行为锁定。"""

import os
import tempfile
import unittest

from cdcparse.events import begin_line, commit_line, data_line, parse_line
from cdcparse.stream import EventReader, FileSource, MemorySource


def order_log():
    return [
        begin_line(1, 7),
        data_line(2, 7, "insert", "orders", {"id": 1}),
        commit_line(3, 7),
    ]


class MemorySourceTest(unittest.TestCase):
    def test_yields_in_given_order(self):
        source = MemorySource(["c", "a", "b"])
        self.assertEqual(list(source), ["c", "a", "b"])

    def test_append_and_len(self):
        source = MemorySource(["x"])
        source.append("y")
        self.assertEqual(len(source), 2)
        self.assertEqual(source.lines(), ["x", "y"])

    def test_iteration_can_be_repeated(self):
        source = MemorySource(["a", "b"])
        self.assertEqual(list(source), list(source))

    def test_snapshot_isolated_from_later_append(self):
        source = MemorySource(["a"])
        walker = iter(source)
        source.append("b")
        self.assertEqual(list(walker), ["a"])


class FileSourceTest(unittest.TestCase):
    def test_reads_lines_and_skips_blanks(self):
        handle, path = tempfile.mkstemp(suffix=".log")
        os.close(handle)
        try:
            with open(path, "w", encoding="utf-8") as out:
                out.write(begin_line(1, 4) + "\n\n" + commit_line(2, 4) + "\n")
            self.assertEqual(list(FileSource(path)), [begin_line(1, 4), commit_line(2, 4)])
        finally:
            os.unlink(path)

    def test_unterminated_tail_is_still_yielded(self):
        handle, path = tempfile.mkstemp(suffix=".log")
        os.close(handle)
        try:
            with open(path, "w", encoding="utf-8") as out:
                out.write(begin_line(1, 4) + "\n" + '{"pos": 2, "type": "com')
            self.assertEqual(len(list(FileSource(path))), 2)
        finally:
            os.unlink(path)


class EventReaderTest(unittest.TestCase):
    def test_reads_events_one_by_one(self):
        reader = EventReader(MemorySource(order_log()))
        events = [reader.read_event(), reader.read_event(), reader.read_event()]
        self.assertEqual([event.kind for event in events],
                         ["begin", "data", "commit"])
        self.assertIsNone(reader.read_event())
        self.assertEqual(reader.arrivals, 3)
        self.assertEqual(reader.position, 3)

    def test_arrival_order_is_not_sorted(self):
        lines = [data_line(3, 7, "insert", "t", {"id": 3}),
                 data_line(1, 7, "insert", "t", {"id": 1}),
                 data_line(2, 7, "insert", "t", {"id": 2})]
        reader = EventReader(MemorySource(lines))
        self.assertEqual([event.pos for event in reader.read_all()], [3, 1, 2])

    def test_read_all_returns_events(self):
        reader = EventReader(MemorySource(order_log()))
        events = reader.read_all()
        self.assertEqual(len(events), 3)
        self.assertIsNone(reader.read_event())

    def test_read_all_on_empty_source(self):
        self.assertEqual(EventReader(MemorySource([])).read_all(), [])

    def test_position_starts_at_zero(self):
        self.assertEqual(EventReader(MemorySource(order_log())).position, 0)

    def test_at_end(self):
        reader = EventReader(MemorySource(order_log()))
        self.assertFalse(reader.at_end())
        reader.read_all()
        self.assertTrue(reader.at_end())

    def test_at_end_on_empty_source(self):
        self.assertTrue(EventReader(MemorySource([])).at_end())

    def test_at_end_does_not_consume(self):
        reader = EventReader(MemorySource(order_log()))
        self.assertFalse(reader.at_end())
        self.assertEqual(reader.read_event().kind, "begin")

    def test_bad_line_raises_with_line_number(self):
        lines = order_log()[:1] + ["not json"] + order_log()[1:]
        reader = EventReader(MemorySource(lines))
        with self.assertRaises(Exception) as caught:
            reader.read_all()
        self.assertIsInstance(caught.exception, ValueError)
        self.assertIn("第 2 行", str(caught.exception))

    def test_truncated_tail_raises(self):
        lines = order_log() + ['{"pos": 4, "type": "data", "xid": 7, "op": "ins']
        with self.assertRaises(ValueError):
            EventReader(MemorySource(lines)).read_all()

    def test_parsed_events_match_payload(self):
        reader = EventReader(MemorySource(order_log()))
        event = reader.read_event()
        reader.read_event()
        self.assertEqual(parse_line(order_log()[0]), event)


if __name__ == "__main__":
    unittest.main()
