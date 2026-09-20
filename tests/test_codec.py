"""规范编码与内容摘要的锁定测试。"""

import unittest

from auditchain.codec import (
    RecordError,
    canonical,
    content_fields,
    decode_line,
    encode_line,
    record_digest,
)


class TestCanonical(unittest.TestCase):
    def test_keys_are_sorted_and_separators_are_tight(self):
        self.assertEqual(canonical({"b": 1, "a": "x"}), b'{"a":"x","b":1}')

    def test_same_content_encodes_to_same_bytes(self):
        first = {"action": "login", "actor": "li", "n": 2}
        second = {"n": 2, "actor": "li", "action": "login"}
        self.assertEqual(canonical(first), canonical(second))

    def test_non_ascii_is_escaped(self):
        self.assertIn(b"\\u5ba1", canonical({"action": "审"}))

    def test_rejects_non_mapping(self):
        for bad in ([1, 2], "text", None, 7):
            with self.assertRaises(RecordError):
                canonical(bad)

    def test_rejects_value_that_json_cannot_encode(self):
        with self.assertRaises(RecordError):
            canonical({"bad": object()})


class TestLineRoundTrip(unittest.TestCase):
    def test_encode_line_ends_with_newline(self):
        blob = encode_line({"seq": 1})
        self.assertTrue(blob.endswith(b"\n"))
        self.assertEqual(blob, b'{"seq":1}\n')

    def test_round_trip_keeps_values(self):
        record = {"seq": 3, "action": "删除", "detail": "a,b:c", "n": 1.5}
        self.assertEqual(decode_line(encode_line(record)), record)

    def test_round_trip_keeps_float_exactly(self):
        record = {"ts": 1700000000.123456}
        self.assertEqual(decode_line(encode_line(record))["ts"], 1700000000.123456)

    def test_decode_rejects_garbage(self):
        for bad in (b"not json\n", b"[1,2]\n", b"\xff\xfe\n", b"\n"):
            with self.assertRaises(RecordError):
                decode_line(bad)

    def test_decode_accepts_str_and_bytes(self):
        self.assertEqual(decode_line('{"a":1}'), {"a": 1})
        self.assertEqual(decode_line(b'{"a":1}'), {"a": 1})


class TestDigest(unittest.TestCase):
    def test_digest_is_stable_and_hex(self):
        record = {"seq": 1, "action": "login"}
        digest = record_digest(record)
        self.assertEqual(digest, record_digest({"action": "login", "seq": 1}))
        self.assertEqual(len(digest), 64)
        int(digest, 16)

    def test_digest_covers_every_content_field(self):
        base = {"seq": 1, "action": "login", "actor": "li"}
        self.assertNotEqual(record_digest(base), record_digest({**base, "actor": "wang"}))
        self.assertNotEqual(record_digest(base), record_digest({**base, "seq": 2}))

    def test_digest_field_itself_is_not_covered(self):
        base = {"seq": 1, "action": "login"}
        with_digest = {**base, "digest": "whatever"}
        self.assertEqual(record_digest(base), record_digest(with_digest))

    def test_content_fields_drops_only_digest(self):
        record = {"seq": 1, "digest": "x"}
        self.assertEqual(content_fields(record), {"seq": 1})


if __name__ == "__main__":
    unittest.main()
