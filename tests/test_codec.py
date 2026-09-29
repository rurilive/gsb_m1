"""朴素恒等编解码器的锁定测试。

只覆盖当前实现已经具备的能力：encode 原样返回输入字节、decode 原样返回
输入字节、任意字节串往返逐字节一致、输出长度等于输入长度、bytes 与
bytearray 都接受、非字节输入抛 TypeError。新增能力（字典、回溯引用、滑动
窗口、变长整数、压缩率、分块与流式解码、损坏流的 fail fast）另开测试文件
test_compress.py，本文件一字不改。
"""

import unittest

from packlex.codec import IdentityCodec


class TestEncode(unittest.TestCase):
    def test_encode_returns_input_bytes(self):
        codec = IdentityCodec()
        self.assertEqual(codec.encode(b"hello"), b"hello")

    def test_encode_empty_is_empty(self):
        codec = IdentityCodec()
        self.assertEqual(codec.encode(b""), b"")

    def test_encode_keeps_length(self):
        codec = IdentityCodec()
        data = bytes(range(256))
        self.assertEqual(len(codec.encode(data)), len(data))

    def test_encode_accepts_bytearray(self):
        codec = IdentityCodec()
        self.assertEqual(codec.encode(bytearray(b"abc")), b"abc")


class TestDecode(unittest.TestCase):
    def test_decode_returns_input_bytes(self):
        codec = IdentityCodec()
        self.assertEqual(codec.decode(b"hello"), b"hello")

    def test_decode_empty_is_empty(self):
        codec = IdentityCodec()
        self.assertEqual(codec.decode(b""), b"")

    def test_decode_accepts_bytearray(self):
        codec = IdentityCodec()
        self.assertEqual(codec.decode(bytearray(b"abc")), b"abc")


class TestRoundTrip(unittest.TestCase):
    def test_round_trip_simple(self):
        codec = IdentityCodec()
        data = b"the quick brown fox"
        self.assertEqual(codec.decode(codec.encode(data)), data)

    def test_round_trip_repeated(self):
        codec = IdentityCodec()
        data = b"ab" * 200
        self.assertEqual(codec.decode(codec.encode(data)), data)

    def test_round_trip_binary(self):
        codec = IdentityCodec()
        data = bytes(range(256)) * 4
        self.assertEqual(codec.decode(codec.encode(data)), data)


class TestValidation(unittest.TestCase):
    def test_encode_rejects_str(self):
        codec = IdentityCodec()
        with self.assertRaises(TypeError):
            codec.encode("text")

    def test_encode_rejects_none(self):
        codec = IdentityCodec()
        with self.assertRaises(TypeError):
            codec.encode(None)

    def test_decode_rejects_str(self):
        codec = IdentityCodec()
        with self.assertRaises(TypeError):
            codec.decode("text")

    def test_decode_rejects_none(self):
        codec = IdentityCodec()
        with self.assertRaises(TypeError):
            codec.decode(None)


if __name__ == "__main__":
    unittest.main()
