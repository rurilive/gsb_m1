"""压缩核的行为基线。"""

import random
import unittest

from msglz import FormatError, lz


class RoundTripTest(unittest.TestCase):
    def test_empty(self):
        blob = lz.compress(b"")
        self.assertEqual(blob, b"")
        self.assertEqual(lz.decompress(blob), b"")

    def test_short_ascii(self):
        data = b"ping"
        self.assertEqual(lz.decompress(lz.compress(data)), data)

    def test_repetitive(self):
        data = b"order.created " * 40
        blob = lz.compress(data)
        self.assertLess(len(blob), len(data) // 4)
        self.assertEqual(lz.decompress(blob), data)

    def test_single_byte_run(self):
        data = b"a" * 500
        blob = lz.compress(data)
        self.assertLess(len(blob), 12)
        self.assertEqual(lz.decompress(blob), data)

    def test_every_byte_value(self):
        data = bytes(range(256)) * 3
        self.assertEqual(lz.decompress(lz.compress(data)), data)

    def test_random_bytes(self):
        data = random.Random(3).randbytes(4096)
        self.assertEqual(lz.decompress(lz.compress(data)), data)

    def test_long_match_is_capped_not_broken(self):
        data = b"abcdefgh" + b"z" * 9000
        self.assertEqual(lz.decompress(lz.compress(data)), data)


class PresetTest(unittest.TestCase):
    def test_hit_into_preset(self):
        preset = b"2026-09-21T07:33:12Z INFO order.paid node=cn-hangzhou-3"
        data = b"2026-09-21T07:33:12Z INFO order.paid node=cn-hangzhou-3 id=48213"
        blob = lz.compress(data, preset=preset)
        self.assertLess(len(blob), len(lz.compress(data)))
        self.assertEqual(lz.decompress(blob, preset=preset), data)

    def test_data_identical_to_preset(self):
        preset = b"alpha-bravo-charlie-delta"
        blob = lz.compress(preset, preset=preset)
        self.assertEqual(lz.decompress(blob, preset=preset), preset)

    def test_preset_without_data(self):
        self.assertEqual(lz.compress(b"", preset=b"whatever"), b"")

    def test_missing_preset_is_rejected(self):
        preset = b"abcdefgh"
        blob = lz.compress(preset, preset=preset)
        with self.assertRaises(FormatError):
            lz.decompress(blob, preset=b"")

    def test_wrong_preset_needs_frame_checksum(self):
        # 换成长度一样的另一本字典，偏移照样成立，解出来是错的但不会报错；
        # 帧里的校验和就是为这种情形准备的。
        preset = b"alpha-bravo"
        data = b"alpha-bravo"
        blob = lz.compress(data, preset=preset)
        other = b"xxxxx-yyyyy"
        self.assertNotEqual(lz.decompress(blob, preset=other), data)


class FormatGuardTest(unittest.TestCase):
    def test_empty_blob(self):
        self.assertEqual(lz.decompress(b""), b"")

    def test_unknown_token(self):
        with self.assertRaises(FormatError):
            lz.decompress(bytes([0x02]))

    def test_truncated_varint(self):
        with self.assertRaises(FormatError):
            lz.decompress(bytes([0x00, 0x80]))

    def test_literal_overruns_stream(self):
        with self.assertRaises(FormatError):
            lz.decompress(bytes([0x00, 0x05, 0x41]))

    def test_zero_offset(self):
        with self.assertRaises(FormatError):
            lz.decompress(bytes([0x01, 0x00, 0x04]))

    def test_offset_beyond_history(self):
        with self.assertRaises(FormatError):
            lz.decompress(bytes([0x01, 0x09, 0x04]))

    def test_zero_length_hit(self):
        blob = lz.compress(b"aaaa")
        with self.assertRaises(FormatError):
            lz.decompress(bytes([0x00, 0x04]) + b"aaaa" + bytes([0x01, 0x04, 0x00]))

    def test_max_size_guard(self):
        data = b"abcdefgh" * 4
        blob = lz.compress(data)
        self.assertEqual(len(lz.decompress(blob, max_size=len(data))), len(data))
        with self.assertRaises(FormatError):
            lz.decompress(blob, max_size=4)


class VarintTest(unittest.TestCase):
    def test_roundtrip(self):
        for value in (0, 1, 127, 128, 300, 65535, 2 ** 20, 2 ** 31):
            blob = lz.encode_varint(value)
            self.assertEqual(lz.decode_varint(blob, 0), (value, len(blob)))

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            lz.encode_varint(-1)

    def test_truncated(self):
        with self.assertRaises(FormatError):
            lz.decode_varint(bytes([0x80]), 0)

    def test_too_long(self):
        with self.assertRaises(FormatError):
            lz.decode_varint(bytes([0x80] * 6), 0)


if __name__ == "__main__":
    unittest.main()
