"""MessageCodec 的行为基线与线上格式兼容基线。

下面两条黄金帧是现网已经在传的字节，编码器不许改出别的形状，
解码器也得一直认得它们。
"""

import random
import unittest

from msglz import FormatError, MessageCodec, frame, lz

#: LZ 路径的黄金帧：b"order.created order.created order.created node=cn-hangzhou-3"
GOLDEN_LZ_MESSAGE = b"order.created order.created order.created node=cn-hangzhou-3"
GOLDEN_LZ_FRAME = bytes.fromhex(
    "4d5a31013c000e6f726465722e6372656174656420010e1c00126e6f64653d"
    "636e2d68616e677a686f752d3348e75f28"
)

#: 直存路径的黄金帧：16 字节压不动的二进制。
GOLDEN_RAW_MESSAGE = bytes(
    [0x9C, 0x2A, 0xF1, 0x03, 0x77, 0xE8, 0x11, 0x5B,
     0xA0, 0x3D, 0xC4, 0x62, 0x8F, 0x19, 0xD6, 0x40]
)
GOLDEN_RAW_FRAME = bytes.fromhex("4d5a3100109c2af10377e8115ba03dc4628f19d6409338cb0f")


class RoundTripTest(unittest.TestCase):
    def setUp(self):
        self.codec = MessageCodec()

    def test_empty_message(self):
        packed = self.codec.encode(b"")
        self.assertEqual(self.codec.decode(packed), b"")
        self.assertEqual(len(packed), len(frame.MAGIC) + 1 + 1 + 4)

    def test_short_ascii(self):
        for message in (b"ping", b"a", b"bus.v2 hello", b"x" * 300):
            self.assertEqual(self.codec.decode(self.codec.encode(message)), message)

    def test_compresses_repetition(self):
        message = b"INVENTORY_SYNC inventory.sync inventory.sync " * 8
        packed = self.codec.encode(message)
        self.assertLess(len(packed), len(message) // 3)
        self.assertEqual(self.codec.decode(packed), message)

    def test_stores_noise_verbatim(self):
        message = random.Random(5).randbytes(200)
        packed = self.codec.encode(message)
        self.assertEqual(frame.unpack_frame(packed)[0], frame.KIND_RAW)
        overhead = len(frame.MAGIC) + 1 + len(lz.encode_varint(len(message))) + 4
        self.assertEqual(len(packed), len(message) + overhead)
        self.assertEqual(self.codec.decode(packed), message)

    def test_many_roundtrips(self):
        rnd = random.Random(11)
        for _ in range(200):
            message = bytes(rnd.randrange(65, 91) for _ in range(rnd.randrange(0, 60)))
            self.assertEqual(self.codec.decode(self.codec.encode(message)), message)


class WireCompatTest(unittest.TestCase):
    def setUp(self):
        self.codec = MessageCodec()

    def test_decodes_old_lz_frame(self):
        self.assertEqual(self.codec.decode(GOLDEN_LZ_FRAME), GOLDEN_LZ_MESSAGE)

    def test_decodes_old_raw_frame(self):
        self.assertEqual(self.codec.decode(GOLDEN_RAW_FRAME), GOLDEN_RAW_MESSAGE)

    def test_encoder_output_is_frozen(self):
        self.assertEqual(self.codec.encode(GOLDEN_LZ_MESSAGE), GOLDEN_LZ_FRAME)
        self.assertEqual(self.codec.encode(GOLDEN_RAW_MESSAGE), GOLDEN_RAW_FRAME)


class CorruptFrameTest(unittest.TestCase):
    def setUp(self):
        self.codec = MessageCodec()
        self.packed = self.codec.encode(b"order.created node=cn-hangzhou-3 " * 4)

    def test_flip_one_payload_byte(self):
        broken = bytearray(self.packed)
        broken[12] ^= 0x20
        with self.assertRaises(FormatError):
            self.codec.decode(bytes(broken))

    def test_truncated_frame(self):
        with self.assertRaises(FormatError):
            self.codec.decode(self.packed[:-1])

    def test_bad_magic(self):
        with self.assertRaises(FormatError):
            self.codec.decode(b"XZ1" + self.packed[3:])

    def test_garbage(self):
        with self.assertRaises(FormatError):
            self.codec.decode(b"not a frame at all, really")


class StatsTest(unittest.TestCase):
    def test_counts_add_up(self):
        codec = MessageCodec()
        messages = [b"alpha" * 3, b"beta", b"gamma" * 2]
        for message in messages:
            codec.encode(message)
        codec.decode(codec.encode(b"delta delta delta"))
        st = codec.stats()
        self.assertEqual(st["messages"], 4)
        self.assertEqual(st["decoded"], 1)
        self.assertEqual(st["raw_bytes"], sum(len(m) for m in messages) + 17)
        self.assertGreater(st["encoded_bytes"], 0)
        self.assertGreater(st["ratio"], 0)

    def test_empty_stats(self):
        st = MessageCodec().stats()
        self.assertEqual(st["messages"], 0)
        self.assertEqual(st["ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
