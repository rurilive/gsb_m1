"""帧结构的打包解包基线。"""

import unittest

from msglz import FormatError, frame


class ChecksumTest(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(frame.fnv32(b""), 0x811C9DC5)
        self.assertEqual(frame.fnv32(b"a"), 0xE40C292C)
        self.assertEqual(frame.fnv32(b"hello world"), 0xD58B3FA7)

    def test_bit_flip_changes_value(self):
        self.assertNotEqual(frame.fnv32(b"order"), frame.fnv32(b"Order"))


class PackTest(unittest.TestCase):
    def test_roundtrip_raw(self):
        payload = b"a short message"
        packed = frame.pack_frame(frame.KIND_RAW, len(payload), payload, frame.fnv32(payload))
        self.assertTrue(packed.startswith(frame.MAGIC))
        kind, raw_len, body, checksum = frame.unpack_frame(packed)
        self.assertEqual((kind, raw_len, body), (frame.KIND_RAW, len(payload), payload))
        self.assertEqual(checksum, frame.fnv32(payload))

    def test_roundtrip_compressed(self):
        payload = b"\x00\x05hello"
        packed = frame.pack_frame(frame.KIND_LZ, 42, payload, 7)
        kind, raw_len, body, checksum = frame.unpack_frame(packed)
        self.assertEqual((kind, raw_len, body, checksum), (frame.KIND_LZ, 42, payload, 7))

    def test_unknown_kind_refused(self):
        with self.assertRaises(ValueError):
            frame.pack_frame(9, 0, b"", 0)


class UnpackGuardTest(unittest.TestCase):
    def make(self, payload=b"hello world"):
        return frame.pack_frame(frame.KIND_RAW, len(payload), payload, frame.fnv32(payload))

    def test_too_short(self):
        with self.assertRaises(FormatError):
            frame.unpack_frame(b"MZ1")

    def test_bad_magic(self):
        packed = b"ZZZ" + self.make()[3:]
        with self.assertRaises(FormatError):
            frame.unpack_frame(packed)

    def test_unknown_kind(self):
        packed = self.make()
        with self.assertRaises(FormatError):
            frame.unpack_frame(packed[:3] + bytes([7]) + packed[4:])

    def test_head_longer_than_frame(self):
        with self.assertRaises(FormatError):
            frame.unpack_frame(bytes([0x4D, 0x5A, 0x31, 0x00, 0x80]))

    def test_unterminated_head_varint(self):
        with self.assertRaises(FormatError):
            frame.unpack_frame(b"MZ1" + bytes([0x00]) + b"\x80" * 8)

    def test_raw_length_mismatch(self):
        payload = b"abc"
        packed = frame.pack_frame(frame.KIND_RAW, 9, payload, 0)
        with self.assertRaises(FormatError):
            frame.unpack_frame(packed)

    def test_lz_length_is_not_checked_here(self):
        # 压缩体的长度靠解压和校验和兜，帧头这层不拦。
        packed = frame.pack_frame(frame.KIND_LZ, 99, b"\x00\x01a", 5)
        kind, raw_len, body, checksum = frame.unpack_frame(packed)
        self.assertEqual((kind, raw_len), (frame.KIND_LZ, 99))


if __name__ == "__main__":
    unittest.main()
