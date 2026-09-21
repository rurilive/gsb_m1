"""Span 记录解析与耗时的基线测试。"""

import unittest

from spanweave.model import Span, SpanError


def record(**overrides):
    base = {
        "trace_id": "tr-1",
        "span_id": "s1",
        "parent_id": "s0",
        "name": "query",
        "service": "mysql",
        "start_ms": 10,
        "end_ms": 30,
    }
    base.update(overrides)
    return base


class TestSpanRecord(unittest.TestCase):

    def test_fields_are_kept(self):
        span = Span.from_record(record())
        self.assertEqual(span.trace_id, "tr-1")
        self.assertEqual(span.span_id, "s1")
        self.assertEqual(span.parent_id, "s0")
        self.assertEqual(span.name, "query")
        self.assertEqual(span.service, "mysql")
        self.assertEqual(span.start_ms, 10)
        self.assertEqual(span.end_ms, 30)

    def test_missing_parent_id_is_none(self):
        span = Span.from_record(record(parent_id=None))
        self.assertIsNone(span.parent_id)

    def test_empty_parent_id_is_none(self):
        span = Span.from_record(record(parent_id=""))
        self.assertIsNone(span.parent_id)

    def test_name_defaults_to_span_id(self):
        span = Span.from_record(record(name=None))
        self.assertEqual(span.name, "s1")

    def test_service_defaults_to_empty(self):
        span = Span.from_record(record(service=None))
        self.assertEqual(span.service, "")

    def test_duration_is_end_minus_start(self):
        span = Span.from_record(record(start_ms=10, end_ms=30))
        self.assertEqual(span.duration_ms, 20)

    def test_zero_duration(self):
        span = Span.from_record(record(start_ms=30, end_ms=30))
        self.assertEqual(span.duration_ms, 0)

    def test_missing_field_raises(self):
        broken = record()
        del broken["end_ms"]
        with self.assertRaises(SpanError):
            Span.from_record(broken)

    def test_non_dict_raises(self):
        with self.assertRaises(SpanError):
            Span.from_record(["tr-1", "s1"])

    def test_empty_ids_raise(self):
        with self.assertRaises(SpanError):
            Span.from_record(record(span_id=""))

    def test_non_integer_timestamps_raise(self):
        with self.assertRaises(SpanError):
            Span.from_record(record(start_ms=1.5))


if __name__ == "__main__":
    unittest.main()
