"""b85x 语义一致性测试：逐条锁定 README《语义约定》。

运行方式（在仓库根目录）：

    python3 -m unittest tests.test_codec -v
    python3 tests/test_codec.py

说明：
- 本文件不依赖 b85x 源码自带常量构造期望值，RFC 字符表/已知向量均按
  README 原文在本文件内独立给出，因此能检出源码字符表被改写的问题。
- 标记 @unittest.expectedFailure 的红用例，其 docstring 上方注释按
  「README 期望 / 实际发生」记录源码与 README 的出入。
- README 未约定的自由行为（如 finish 之后再 feed）不做断言。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from b85x import (
    Base32Decoder,
    Base32Encoder,
    Base85Decoder,
    Base85Encoder,
    CodecError,
)

# README 第 2 节原文给出的两张字符表（独立于源码再写一遍）。
B85_ALPHABET = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "!#$%&()*+-;<=>?@^_`{|}~"
)
B32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def b85_encode_once(data):
    """按 README 第 3 节规则独立实现的一次性 Base85 编码，作为对照基准。"""
    out = []
    for i in range(0, len(data) - len(data) % 4, 4):
        value = int.from_bytes(data[i:i + 4], "big")
        chars = ""
        for power in (85 ** 4, 85 ** 3, 85 ** 2, 85, 1):
            chars += B85_ALPHABET[value // power % 85]
        out.append(chars)
    tail = len(data) % 4
    if tail:
        value = int.from_bytes(data[-tail:] + b"\x00" * (4 - tail), "big")
        chars = ""
        for power in (85 ** 4, 85 ** 3, 85 ** 2, 85, 1):
            chars += B85_ALPHABET[value // power % 85]
        out.append(chars[:tail + 1])
    return "".join(out)


def b85_decode_once(text):
    """按 README 第 4 节规则独立实现的一次性 Base85 解码，作为对照基准。"""
    for ch in text:
        if ch not in B85_ALPHABET:
            raise CodecError("illegal character: %r" % ch)
    out = bytearray()
    for i in range(0, len(text) - len(text) % 5, 5):
        value = 0
        for ch in text[i:i + 5]:
            value = value * 85 + B85_ALPHABET.index(ch)
        if value > 0xFFFFFFFF:
            raise CodecError("group value overflows 32 bits")
        out += value.to_bytes(4, "big")
    tail = len(text) % 5
    if tail == 1:
        raise CodecError("lone trailing character cannot be decoded")
    if tail:
        value = 0
        for ch in text[-tail:] + "~" * (5 - tail):
            value = value * 85 + B85_ALPHABET.index(ch)
        out += value.to_bytes(4, "big")[:tail - 1]
    return bytes(out)


def b32_encode_once(data):
    """按 README 第 5 节规则独立实现的一次性 Base32 编码，作为对照基准。"""
    out = []
    for i in range(0, len(data) - len(data) % 5, 5):
        value = int.from_bytes(data[i:i + 5], "big")
        out.append("".join(B32_ALPHABET[value >> s & 31]
                           for s in (35, 30, 25, 20, 15, 10, 5, 0)))
    tail = len(data) % 5
    if tail:
        value = int.from_bytes(data[-tail:] + b"\x00" * (5 - tail), "big")
        chars = "".join(B32_ALPHABET[value >> s & 31]
                        for s in (35, 30, 25, 20, 15, 10, 5, 0))
        out.append(chars[:(tail * 8 + 4) // 5])
    return "".join(out)


def b32_decode_once(text):
    """按 README 第 6 节规则独立实现的一次性 Base32 解码，作为对照基准。"""
    for ch in text:
        if ch not in B32_ALPHABET:
            raise CodecError("illegal character: %r" % ch)
    out = bytearray()
    for i in range(0, len(text) - len(text) % 8, 8):
        value = 0
        for ch in text[i:i + 8]:
            value = value << 5 | B32_ALPHABET.index(ch)
        out += value.to_bytes(5, "big")
    tail = len(text) % 8
    if tail and tail not in (2, 4, 5, 7):
        raise CodecError("invalid tail length: %d" % tail)
    if tail:
        value = 0
        for ch in text[-tail:]:
            value = value << 5 | B32_ALPHABET.index(ch)
        count = tail * 5 // 8
        out += (value >> (tail * 5 - count * 8)).to_bytes(count, "big")
    return bytes(out)


def stream_encode(encoder_class, data, cuts):
    """按 cuts 边界分块喂入编码器，拼接各次 feed 返回值与 finish 结果。"""
    encoder = encoder_class()
    parts = []
    pos = 0
    for size in cuts:
        parts.append(encoder.encode_feed(data[pos:pos + size]))
        pos += size
    parts.append(encoder.finish())
    return "".join(parts)


def stream_decode(decoder_class, text, cuts):
    """按 cuts 边界分块喂入解码器，拼接各次 feed 返回值与 finish 结果。"""
    decoder = decoder_class()
    parts = []
    pos = 0
    for size in cuts:
        parts.append(decoder.decode_feed(text[pos:pos + size]))
        pos += size
    parts.append(decoder.finish())
    return b"".join(parts)


class AlphabetTests(unittest.TestCase):
    """README 第 2 节：字符表。"""

    def test_b85_alphabet_is_rfc1924(self):
        from b85x import base85
        self.assertEqual(len(base85.ALPHABET), 85)
        self.assertEqual(base85.ALPHABET, B85_ALPHABET)

    # README 期望：Base32 字符表即 RFC 4648，第 12、13 位应为 "MN"。
    # 实际发生：b85x/base32.py 的 ALPHABET 写成 "...JKLNMOP..."，
    # M、N 位置互换，所有编解码结果整体偏离 RFC 4648。
    @unittest.expectedFailure
    def test_b32_alphabet_is_rfc4648(self):
        from b85x import base32
        self.assertEqual(len(base32.ALPHABET), 32)
        self.assertEqual(base32.ALPHABET, B32_ALPHABET)


class CommonTests(unittest.TestCase):
    """README 第 1 节：异常类型与流式基本约定。"""

    def test_codec_error_is_value_error(self):
        self.assertTrue(issubclass(CodecError, ValueError))

    def test_feeds_callable_many_times(self):
        data = b"abcdefgh"
        text = stream_encode(Base85Encoder, data, (4, 4))
        self.assertEqual(text, b85_encode_once(data))
        self.assertEqual(stream_decode(Base85Decoder, text, (3, 4, 3)), data)

    def test_empty_input(self):
        for encoder_class, decoder_class in (
            (Base85Encoder, Base85Decoder),
            (Base32Encoder, Base32Decoder),
        ):
            self.assertEqual(stream_encode(encoder_class, b"", (0,)), "")
            self.assertEqual(stream_decode(decoder_class, "", (0,)), b"")


class B85KnownAnswerTests(unittest.TestCase):
    """README 第 3、4 节：Base85 编码/解码已知向量与 padding 规则。"""

    def test_encode_full_groups(self):
        self.assertEqual(b85_encode_once(b"hell"), "Xk~0{")
        self.assertEqual(stream_encode(Base85Encoder, b"hell", (4,)), "Xk~0{")

    def test_encode_zero_group_has_no_z_shortcut(self):
        # README：无 z 特例，全零组也按普通 5 字符输出 "00000"。
        self.assertEqual(
            stream_encode(Base85Encoder, b"\x00\x00\x00\x00", (4,)),
            "00000",
        )

    def test_encode_tail_n1(self):
        # n=1：补零整组编码取前 n+1=2 个字符。
        self.assertEqual(stream_encode(Base85Encoder, b"h", (1,)), "Xa")

    def test_encode_tail_n2(self):
        # n=2：补零整组编码取前 n+1=3 个字符。
        self.assertEqual(stream_encode(Base85Encoder, b"he", (2,)), "Xk`")

    # README 期望：尾长 n=3 时取整组编码的前 n+1=4 个字符（"hel" -> "Xk}~"）。
    # 实际发生：b85x/base85.py 的 finish 用 (n+1)%4 切片，n=3 时切成 0，
    # 尾块输出为空，带 3 字节尾的报文静默丢尾。
    @unittest.expectedFailure
    def test_encode_tail_n3(self):
        self.assertEqual(stream_encode(Base85Encoder, b"hel", (3,)), "Xk}~")

    def test_encode_mixed_groups_and_tail(self):
        self.assertEqual(b85_encode_once(b"hello"), "Xk~0{Zv")
        self.assertEqual(
            stream_encode(Base85Encoder, b"hello", (5,)), "Xk~0{Zv"
        )

    def test_decode_full_groups(self):
        self.assertEqual(stream_decode(Base85Decoder, "Xk~0{", (5,)), b"hell")

    def test_decode_tail_lengths_2_to_4_padded_with_tilde(self):
        # README 第 4 节：m 属于 2..4 时用 '~' 补到 5 位，取前 m-1 字节。
        for text, expected in (
            ("Xa", b"h"),
            ("Xk`", b"he"),
            ("Xk}~", b"hel"),
        ):
            self.assertEqual(
                stream_decode(Base85Decoder, text, (len(text),)), expected
            )

    def test_decode_group_overflow_raises(self):
        # "~~~~~" 对应 85**5-1，超过 32 位无符号上限，feed 时即抛。
        decoder = Base85Decoder()
        with self.assertRaises(CodecError):
            decoder.decode_feed("~~~~~")

    def test_decode_lone_trailing_char_raises(self):
        for bad in ("0", "z"):
            decoder = Base85Decoder()
            decoder.decode_feed(bad)
            with self.assertRaises(CodecError):
                decoder.finish()

    def test_decode_illegal_char_raises(self):
        # 'z' 在 RFC 1924 字符表内（无 z 特例只是没有全零缩写）；
        # 这里只钉真正不在字符表里的字符（部分非法字符落在尾块，
        # finish 时才抛出）。
        for bad in ("=", "0000:", "ab,cd", "[x]"):
            decoder = Base85Decoder()
            with self.assertRaises(CodecError):
                decoder.decode_feed(bad)
                decoder.finish()

    def test_decode_z_is_regular_character(self):
        # README 第 2 节：无 z 特例，"zzzzz" 按普通组解而非全零组。
        text = "zzzzz"
        result = stream_decode(Base85Decoder, text, (5,))
        self.assertEqual(result, b85_decode_once(text))
        self.assertNotEqual(result, b"\x00\x00\x00\x00")

    # README 期望：字符表以外的任何字符（包括空格、\t、\r、\n 等空白）
    # 必须立即抛 CodecError，不得跳过或忽略。
    # 实际发生：b85x/base85.py 的 decode_feed 先用生成式过滤空白，
    # "Xk ~0{\n" 被静默清洗后解成 b"hell"，对账内容被悄悄改写。
    @unittest.expectedFailure
    def test_decode_whitespace_must_raise_immediately(self):
        for bad in ("Xk ~0{", "Xk\t~0{", "Xk\r~0{", "Xk\n~0{"):
            decoder = Base85Decoder()
            with self.assertRaises(CodecError):
                decoder.decode_feed(bad)


class B32KnownAnswerTests(unittest.TestCase):
    """README 第 5、6 节：Base32 编码/解码已知向量与尾长规则。"""

    # README 期望：Base32 用 RFC 4648 字符表，"foo" 编码为 "MZXW6"。
    # 实际发生：源码字符表 M/N 写反，编码出 "NZXW6"。
    @unittest.expectedFailure
    def test_encode_rfc4648_vectors(self):
        cases = (
            (b"f", "MY"),
            (b"fo", "MZXQ"),
            (b"foo", "MZXW6"),
            (b"foob", "MZXW6YQ"),
            (b"foeba", "MZXW6YTB"),
            (b"foobar", "MZXW6YTBOI"),
        )
        for data, expected in cases:
            self.assertEqual(
                stream_encode(Base32Encoder, data, (len(data),)), expected
            )

    # README 期望：解码同样遵循 RFC 4648，"MY" 解出 b"f"。
    # 实际发生：字符表错位后 "MY" 解出 b"n"，合法编码无法正确还原。
    @unittest.expectedFailure
    def test_decode_rfc4648_vectors(self):
        for text, expected in (
            ("MY", b"f"),
            ("MZXW6", b"foo"),
            ("MZXW6YTBOI", b"foobar"),
        ):
            self.assertEqual(
                stream_decode(Base32Decoder, text, (len(text),)), expected
            )

    def test_encode_no_equals_padding(self):
        # README：本包不使用 '=' padding；尾长 1..4 输出长度分别为
        # ceil(n*8/5) = 2/4/5/7。
        for size, length in ((1, 2), (2, 4), (3, 5), (4, 7)):
            text = stream_encode(Base32Encoder, b"\x01" * size, (size,))
            self.assertEqual(len(text), length)
            self.assertNotIn("=", text)

    def test_encode_bit_order_big_endian(self):
        # README：标准 5 位组大端拼接。该向量不含 M/N，不受字符表
        # 错位影响，单独锁定位序。
        data = b"\x01\x02"
        self.assertEqual(
            stream_encode(Base32Encoder, data, (2,)), b32_encode_once(data)
        )

    def test_decode_illegal_char_raises(self):
        for bad in ("0", "mzxw6", "MZXW6=", "MZX W6"):
            decoder = Base32Decoder()
            with self.assertRaises(CodecError):
                decoder.decode_feed(bad)

    def test_decode_tail_allowed_lengths(self):
        # README：尾长 m 属于 {2,4,5,7} 时解出 floor(m*5/8) 字节。
        for text, length in (("MY", 1), ("MZXQ", 2), ("MZXW6", 3),
                             ("MZXW6YQ", 4)):
            decoder = Base32Decoder()
            decoder.decode_feed(text)
            self.assertEqual(len(decoder.finish()), length)

    def test_decode_tail_bad_lengths_raise(self):
        # README：其余尾长 {1,3,6} 抛 CodecError。
        for bad in ("M", "MZX", "MZXW6Y"):
            decoder = Base32Decoder()
            decoder.decode_feed(bad)
            with self.assertRaises(CodecError):
                decoder.finish()


class StreamBoundaryTests(unittest.TestCase):
    """README 第 1 节：流式边界无关性。

    同一输入按任意边界分块：各次 feed 返回值拼接 finish 结果，必须与
    一次性处理整段输入完全一致；解码同理。
    """

    BOUNDARY_PAYLOAD = bytes((i * 37 + 11) % 256 for i in range(12))
    BOUNDARY_CUTS = ((1,) * 12,
                     (3, 5, 2, 2),
                     (2, 2, 2, 2, 2, 2),
                     (4, 4, 4),
                     (12,))

    # README 期望：Base85 编码任意分块结果 == 一次性结果。
    # 实际发生：b85x/base85.py 的 encode_feed 写成 self._carry += buf，
    # 上轮残留被重复拼接，非 4 倍数边界（如 3+5+2+3）输出重复/错组。
    @unittest.expectedFailure
    def test_b85_encode_chunk_independent(self):
        encoder = Base85Encoder()
        whole = encoder.encode_feed(self.BOUNDARY_PAYLOAD) + encoder.finish()
        for cuts in self.BOUNDARY_CUTS:
            self.assertEqual(
                stream_encode(Base85Encoder, self.BOUNDARY_PAYLOAD, cuts),
                whole,
            )

    def test_b85_decode_chunk_independent(self):
        text = b85_encode_once(self.BOUNDARY_PAYLOAD)
        self.assertEqual(len(text), 15)  # 12 字节 = 3 整组共 15 字符
        decoder = Base85Decoder()
        whole = decoder.decode_feed(text) + decoder.finish()
        cuts85 = ((1,) * 15, (3, 5, 7), (5, 5, 5))
        for cuts in cuts85:
            self.assertEqual(sum(cuts), len(text))
            self.assertEqual(
                stream_decode(Base85Decoder, text, cuts), whole
            )

    def test_b32_encode_chunk_independent(self):
        data = b"gateway-frame!!"  # 15 字节：整组 + 各类边界
        encoder = Base32Encoder()
        whole = encoder.encode_feed(data) + encoder.finish()
        for cuts in ((1,) * 15, (3, 4, 2, 4, 2), (7, 1, 7), (15,)):
            self.assertEqual(stream_encode(Base32Encoder, data, cuts), whole)

    def test_b32_decode_chunk_independent(self):
        encoder = Base32Encoder()
        text = encoder.encode_feed(b"gateway-frame!!") + encoder.finish()
        self.assertEqual(len(text) % 8, 0)  # 15 字节整组 24 字符
        decoder = Base32Decoder()
        whole = decoder.decode_feed(text) + decoder.finish()
        for cuts in ((1,) * len(text), (3, 5, 7, 9), (8, 8, 8),
                     (len(text),)):
            self.assertEqual(sum(cuts), len(text))
            self.assertEqual(stream_decode(Base32Decoder, text, cuts), whole)


class CrossCheckTests(unittest.TestCase):
    """与本文件内独立实现的 README 基准实现做交叉校验。"""

    SAMPLE = bytes((i * 53 + 7) % 256 for i in range(31))

    def test_b85_decode_agrees_with_readme_reference(self):
        # 用 README 基准实现编码，源码解码器应能在各种尾长下还原原文。
        for size in range(0, 12):
            data = self.SAMPLE[:size]
            text = b85_encode_once(data)
            decoder = Base85Decoder()
            self.assertEqual(decoder.decode_feed(text) + decoder.finish(),
                             data)

    def test_b32_decode_agrees_with_readme_reference_lengths(self):
        # 字符表错位不影响尾长规则；校验各种长度下输出字节数（整组
        # 字节在 decode_feed 返回，尾块字节在 finish 返回，需拼接）。
        for size in range(1, 10):
            text = b32_encode_once(self.SAMPLE[:size])
            decoder = Base32Decoder()
            output = decoder.decode_feed(text) + decoder.finish()
            self.assertEqual(len(output), size, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
