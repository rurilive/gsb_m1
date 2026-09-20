"""16 字节定长记录的编解码基线。"""

import unittest

from wirepack.errors import DecodeError, EncodeError
from wirepack.records import (
    LABEL_SIZE,
    MAX_SEQ,
    RECORD_SIZE,
    Record,
    decode_label,
    encode_label,
    pack_record,
    unpack_record,
)


class LabelTest(unittest.TestCase):
    def test_short_label_is_padded(self):
        self.assertEqual(encode_label("aa"), b"aa" + b"\x00" * 8)

    def test_full_label_is_not_padded(self):
        raw = encode_label("0123456789")
        self.assertEqual(len(raw), LABEL_SIZE)
        self.assertEqual(raw, b"0123456789")

    def test_empty_label(self):
        self.assertEqual(encode_label(""), b"\x00" * LABEL_SIZE)

    def test_too_long_label_rejected(self):
        with self.assertRaises(EncodeError):
            encode_label("0123456789a")

    def test_non_ascii_label_rejected(self):
        with self.assertRaises(EncodeError):
            encode_label("订单")

    def test_non_string_label_rejected(self):
        with self.assertRaises(EncodeError):
            encode_label(b"raw")

    def test_decode_strips_padding(self):
        self.assertEqual(decode_label(b"ok" + b"\x00" * 8), "ok")

    def test_decode_rejects_dirty_padding(self):
        with self.assertRaises(DecodeError) as caught:
            decode_label(b"ok\x00x\x00\x00\x00\x00\x00\x00")
        self.assertEqual(caught.exception.field, "label")

    def test_decode_rejects_non_ascii(self):
        with self.assertRaises(DecodeError):
            decode_label(b"\xff\xfe" + b"\x00" * 8)


class PackTest(unittest.TestCase):
    def test_record_is_sixteen_bytes(self):
        raw = pack_record(Record(7, "data", "a"))
        self.assertEqual(len(raw), RECORD_SIZE)
        self.assertIsInstance(raw, bytes)

    def test_layout_is_big_endian(self):
        raw = pack_record(Record(0x0001ABCD, "ack", "hi", flags=5))
        self.assertEqual(raw[:4], b"\x00\x01\xab\xcd")
        self.assertEqual(raw[4], 2)
        self.assertEqual(raw[5], 5)
        self.assertEqual(raw[6:8], b"hi")
        self.assertEqual(raw[8:], b"\x00" * 8)

    def test_first_byte_is_always_zero(self):
        for seq in (0, 1, 0x7A11FF, MAX_SEQ - 1):
            self.assertEqual(pack_record(Record(seq, "data"))[0], 0)

    def test_kind_codes(self):
        for code, kind in ((1, "data"), (2, "ack"), (3, "ctrl")):
            self.assertEqual(pack_record(Record(1, kind))[4], code)

    def test_max_seq_ok(self):
        raw = pack_record(Record(MAX_SEQ - 1, "data"))
        self.assertEqual(len(raw), RECORD_SIZE)

    def test_seq_at_limit_rejected(self):
        with self.assertRaises(EncodeError):
            pack_record(Record(MAX_SEQ, "data"))

    def test_negative_seq_rejected(self):
        with self.assertRaises(EncodeError):
            pack_record(Record(-1, "data"))

    def test_bool_seq_rejected(self):
        with self.assertRaises(EncodeError):
            pack_record(Record(True, "data"))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(EncodeError):
            pack_record(Record(1, "shrug"))

    def test_flags_range(self):
        self.assertEqual(pack_record(Record(1, "data", flags=255))[5], 255)
        with self.assertRaises(EncodeError):
            pack_record(Record(1, "data", flags=256))
        with self.assertRaises(EncodeError):
            pack_record(Record(1, "data", flags=True))


class UnpackTest(unittest.TestCase):
    def test_roundtrip(self):
        record = Record(123456, "ctrl", "node-1", flags=9)
        back, end = unpack_record(pack_record(record))
        self.assertEqual(back, record)
        self.assertEqual(end, RECORD_SIZE)

    def test_roundtrip_from_offset(self):
        blob = b"\xff\xff" + pack_record(Record(5, "ack", "x"))
        back, end = unpack_record(blob, 2)
        self.assertEqual(back, Record(5, "ack", "x"))
        self.assertEqual(end, 2 + RECORD_SIZE)

    def test_short_buffer_raises(self):
        with self.assertRaises(DecodeError) as caught:
            unpack_record(b"\x00" * 15)
        self.assertEqual(caught.exception.offset, 0)
        self.assertEqual(caught.exception.field, "record")

    def test_short_buffer_from_offset_raises(self):
        with self.assertRaises(DecodeError) as caught:
            unpack_record(b"\x00" * 20, 5)
        self.assertEqual(caught.exception.offset, 5)

    def test_out_of_range_seq_raises(self):
        raw = b"\xff" + pack_record(Record(1, "data"))[1:]
        with self.assertRaises(DecodeError) as caught:
            unpack_record(raw, 0)
        self.assertEqual(caught.exception.field, "seq")

    def test_unknown_kind_code_raises(self):
        raw = b"\x00\x00\x00\x01" + b"\x09" + b"\x00" * 11
        with self.assertRaises(DecodeError) as caught:
            unpack_record(raw)
        self.assertEqual(caught.exception.field, "kind")
        self.assertEqual(caught.exception.offset, 4)

    def test_dirty_label_padding_raises(self):
        raw = b"\x00\x00\x00\x01" + b"\x01\x00" + b"a\x00b" + b"\x00" * 7
        with self.assertRaises(DecodeError) as caught:
            unpack_record(raw)
        self.assertEqual(caught.exception.field, "label")
        self.assertEqual(caught.exception.offset, 6)

    def test_accepts_bytearray_and_memoryview(self):
        raw = pack_record(Record(3, "data", "z"))
        self.assertEqual(unpack_record(bytearray(raw))[0].seq, 3)
        self.assertEqual(unpack_record(memoryview(raw))[0].seq, 3)


class RecordTest(unittest.TestCase):
    def test_equality_ignores_nothing(self):
        self.assertEqual(Record(1, "data", "a", 1), Record(1, "data", "a", 1))
        self.assertNotEqual(Record(1, "data", "a", 1), Record(1, "data", "a", 2))
        self.assertNotEqual(Record(1, "data", "a"), Record(2, "data", "a"))

    def test_equality_with_other_types(self):
        self.assertNotEqual(Record(1, "data"), "Record")

    def test_repr_mentions_fields(self):
        self.assertIn("seq=1", repr(Record(1, "data")))

    def test_hashable(self):
        self.assertEqual(len({Record(1, "data"), Record(1, "data")}), 1)


if __name__ == "__main__":
    unittest.main()
