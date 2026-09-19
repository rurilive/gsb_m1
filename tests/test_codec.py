"""b85x 语义测试：逐条锁定 README「语义约定」。

运行方式（仓库根目录或任意目录均可）：
    python3 -m unittest tests.test_codec
    python3 tests/test_codec.py

红用例上方的注释写明「README 期望什么 / 实际发生什么」。
"""

import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from b85x import (  # noqa: E402
    Base32Decoder,
    Base32Encoder,
    Base85Decoder,
    Base85Encoder,
    CodecError,
)
from b85x import base32, base85  # noqa: E402

RFC1924_ALPHABET = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "!#$%&()*+-;<=>?@^_`{|}~"
)
RFC4648_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

# RFC 4648 官方测试向量（去掉本包不使用的 '=' padding）
RFC4648_VECTORS = [
    (b"", ""),
    (b"f", "MY"),
    (b"fo", "MZXQ"),
    (b"foo", "MZXW6"),
    (b"foob", "MZXW6YQ"),
    (b"fooba", "MZXW6YTB"),
    (b"foobar", "MZXW6YTBOI"),
]


def encode_all(enc_cls, data, chunk=None):
    """一次性或按固定块长喂入，拼接各次 feed 与 finish 的输出。"""
    enc = enc_cls()
    if chunk is None:
        return enc.encode_feed(data) + enc.finish()
    parts = [enc.encode_feed(data[i:i + chunk])
             for i in range(0, len(data), chunk)]
    parts.append(enc.finish())
    return "".join(parts)


def decode_all(dec_cls, text, chunk=None):
    dec = dec_cls()
    if chunk is None:
        return dec.decode_feed(text) + dec.finish()
    parts = [dec.decode_feed(text[i:i + chunk])
             for i in range(0, len(text), chunk)]
    parts.append(dec.finish())
    return b"".join(parts)


class TestAlphabets(unittest.TestCase):
    """README 第 2 条：字符表。"""

    def test_base85_alphabet_is_rfc1924(self):
        self.assertEqual(base85.ALPHABET, RFC1924_ALPHABET)
        self.assertEqual(len(base85.ALPHABET), 85)
        self.assertEqual(len(set(base85.ALPHABET)), 85)

    # README 期望：Base32 字符表为 RFC 4648（A-Z 加 2-7）。
    # 实际发生：base32.ALPHABET 为 "ABCDEFGHIJKLNMOPQRSTUVWXYZ234567"，
    # 'M' 与 'N' 位置互换，编解码出的字符流与 RFC 4648 对端对不上。
    def test_base32_alphabet_is_rfc4648(self):
        self.assertEqual(base32.ALPHABET, RFC4648_ALPHABET)
        self.assertEqual(len(base32.ALPHABET), 32)
        self.assertEqual(len(set(base32.ALPHABET)), 32)


class TestBase85Encode(unittest.TestCase):
    """README 第 3 条：Base85 编码。"""

    def test_full_group_known_vectors(self):
        # 全零组按普通 5 字符输出，无 'z' 特例
        self.assertEqual(encode_all(Base85Encoder, b"\x00\x00\x00\x00"), "00000")
        self.assertEqual(encode_all(Base85Encoder, b"\xff\xff\xff\xff"), "|NsC0")
        self.assertEqual(
            encode_all(Base85Encoder, b"gateway-frame-0042"),
            base64.b85encode(b"gateway-frame-0042").decode(),
        )

    def test_full_groups_match_stdlib(self):
        for length in (4, 8, 40):
            data = bytes(range(length))
            self.assertEqual(
                encode_all(Base85Encoder, data),
                base64.b85encode(data).decode(),
            )

    def test_tail_padding_n1_n2(self):
        # 尾长 n 补 \x00 后取前 n+1 字符
        self.assertEqual(encode_all(Base85Encoder, b"f"), "W&")       # n=1 -> 2
        self.assertEqual(encode_all(Base85Encoder, b"fo"), "W^V")     # n=2 -> 3

    # README 期望：尾长 n=3 时取整组编码的前 n+1=4 个字符（如 b"foo" -> "W^Zo"）。
    # 实际发生：finish 中截取长度为 (n+1) % 4，n=3 时得 0，尾组输出为空串，
    # 长度 ≡ 3 (mod 4) 的报文尾部 3 字节在编码端凭空丢失。
    def test_tail_padding_n3(self):
        self.assertEqual(encode_all(Base85Encoder, b"foo"), "W^Zo")   # n=3 -> 4
        self.assertEqual(
            encode_all(Base85Encoder, b"foobar"),
            base64.b85encode(b"foobar").decode(),
        )


class TestBase85Decode(unittest.TestCase):
    """README 第 4 条：Base85 解码。"""

    def test_known_vectors(self):
        self.assertEqual(decode_all(Base85Decoder, "00000"), b"\x00" * 4)
        self.assertEqual(decode_all(Base85Decoder, "|NsC0"), b"\xff" * 4)

    def test_tail_lengths(self):
        # 结尾 m 个字符（2 <= m <= 4）补 '~' 后取前 m-1 字节
        self.assertEqual(decode_all(Base85Decoder, "W&"), b"f")
        self.assertEqual(decode_all(Base85Decoder, "W^V"), b"fo")
        self.assertEqual(decode_all(Base85Decoder, "W^Zo"), b"foo")

    def test_lone_trailing_char_raises(self):
        with self.assertRaises(CodecError):
            decode_all(Base85Decoder, "W")

    def test_overflow_group_raises(self):
        # 85**5 - 1 > 2**32 - 1，组值溢出必须抛 CodecError
        with self.assertRaises(CodecError):
            decode_all(Base85Decoder, "~~~~~")

    def test_illegal_char_raises_immediately(self):
        dec = Base85Decoder()
        with self.assertRaises(CodecError):
            dec.decode_feed('W,Zo')  # ',' 不在字符表中，应立即抛出
        self.assertIsInstance(CodecError("x"), ValueError)

    # README 期望：解码端对字符表以外的任何字符（包括空格、\t、\r、\n
    # 等空白）必须立即抛 CodecError，不得跳过或忽略。
    # 实际发生：decode_feed 先过滤 _WS 再校验，空白被静默丢弃，
    # "W^Z o" 被当作 "W^Zo" 解出 b"foo"，坏帧不会被发现。
    def test_whitespace_raises(self):
        for text in ("W^Z o", "W^Zo\n", "\tW^Zo", "W^\r\nZo"):
            with self.subTest(text=text):
                with self.assertRaises(CodecError):
                    decode_all(Base85Decoder, text)


class TestBase85Streaming(unittest.TestCase):
    """README 第 1 条：流式边界无关性（Base85）。"""

    # README 期望：同一输入按任意边界分块，各次 feed 返回值拼接 finish
    # 的结果与一次性处理完全一致。
    # 实际发生：encode_feed 用 `self._carry += buf` 累加残余，而 buf 已
    # 包含旧 carry，导致旧残余被重复保留；只要某次 feed 留下非空 carry，
    # 后续输出就会多出重复分组（分块发大报文时两端对不上的根因）。
    def test_encode_chunk_boundary_independence(self):
        payload = bytes(range(1, 33))  # 32 字节，避开尾组缺陷干扰
        one_shot = encode_all(Base85Encoder, payload)
        for chunk in (1, 2, 3, 5, 7, 11):
            with self.subTest(chunk=chunk):
                self.assertEqual(
                    encode_all(Base85Encoder, payload, chunk), one_shot)

    def test_decode_chunk_boundary_independence(self):
        text = base64.b85encode(bytes(range(1, 33))).decode()
        one_shot = decode_all(Base85Decoder, text)
        for chunk in (1, 2, 3, 6, 13):
            with self.subTest(chunk=chunk):
                self.assertEqual(
                    decode_all(Base85Decoder, text, chunk), one_shot)

    # README 期望：按 README 第 3、4 条规则，任意长度报文编码后再解码
    # 应还原原文。
    # 实际发生：长度 ≡ 3 (mod 4) 的报文因尾组输出空串（见
    # TestBase85Encode.test_tail_padding_n3）roundtrip 后丢失尾部 3 字节。
    def test_roundtrip_various_lengths(self):
        for length in range(0, 21):
            data = bytes(range(length))
            with self.subTest(length=length):
                text = encode_all(Base85Encoder, data)
                self.assertEqual(decode_all(Base85Decoder, text), data)


class TestBase32Encode(unittest.TestCase):
    """README 第 5 条：Base32 编码。"""

    # README 期望：RFC 4648 字符表与位序，b"f"->"MY"、b"foo"->"MZXW6" 等。
    # 实际发生：字符表 M/N 互换，b"foo" 编成 "NZXW6"，所有含索引 11/12
    # 的编码输出都与 RFC 4648 对端不一致。
    def test_rfc4648_vectors(self):
        for raw, text in RFC4648_VECTORS:
            with self.subTest(raw=raw):
                self.assertEqual(encode_all(Base32Encoder, raw), text)

    def test_tail_length_rule(self):
        # 尾长 n -> ceil(n*8/5) 个字符，不使用 '=' padding
        for n, out_len in ((1, 2), (2, 4), (3, 5), (4, 7)):
            with self.subTest(n=n):
                self.assertEqual(
                    len(encode_all(Base32Encoder, bytes(range(n)))), out_len)

    def test_encode_chunk_boundary_independence(self):
        payload = bytes(range(1, 21))  # 20 字节，5 的倍数
        one_shot = encode_all(Base32Encoder, payload)
        for chunk in (1, 2, 3, 4, 6, 7, 9):
            with self.subTest(chunk=chunk):
                self.assertEqual(
                    encode_all(Base32Encoder, payload, chunk), one_shot)


class TestBase32Decode(unittest.TestCase):
    """README 第 6 条：Base32 解码。"""

    # README 期望：按 RFC 4648 字符表解码，"MZXW6" -> b"foo" 等。
    # 实际发生：字符表 M/N 互换，"MZXW6" 解出的字节与原文不符，
    # 与 RFC 4648 对端发来的合法报文对不上。
    def test_rfc4648_vectors(self):
        for raw, text in RFC4648_VECTORS:
            with self.subTest(text=text):
                self.assertEqual(decode_all(Base32Decoder, text), raw)

    def test_tail_length_validation(self):
        # 尾长仅允许 {2, 4, 5, 7}，其余抛 CodecError
        for m in (1, 3, 6):
            with self.subTest(m=m):
                with self.assertRaises(CodecError):
                    decode_all(Base32Decoder, "A" * m)
        for m in (2, 4, 5, 7):
            with self.subTest(m=m):
                decode_all(Base32Decoder, "A" * m)  # 不抛即通过

    def test_illegal_char_raises(self):
        for text in ("MZXW6YQ=", "mzxw6", "MZXW 6", "MZXW6\n"):
            with self.subTest(text=text):
                with self.assertRaises(CodecError):
                    decode_all(Base32Decoder, text)

    def test_decode_chunk_boundary_independence(self):
        text = encode_all(Base32Encoder, bytes(range(1, 21)))
        one_shot = decode_all(Base32Decoder, text)
        for chunk in (1, 2, 3, 5, 9):
            with self.subTest(chunk=chunk):
                self.assertEqual(
                    decode_all(Base32Decoder, text, chunk), one_shot)

    def test_roundtrip_various_lengths(self):
        # 字符表缺陷对编解码两端对称，自洽 roundtrip 不受影响，
        # 该用例应为绿（字符表问题由 RFC 4648 向量用例锁定）。
        for length in range(0, 13):
            data = bytes(range(length))
            with self.subTest(length=length):
                text = encode_all(Base32Encoder, data)
                self.assertEqual(decode_all(Base32Decoder, text), data)


if __name__ == "__main__":
    unittest.main()
