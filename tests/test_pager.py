"""分页编码的单元行为：页头 min/max、字典复用、单页自解、坏页与压缩。"""

import struct
import unittest
import zlib

from colpage.errors import BadPageError, FormatError
from colpage.pager import (
    ENC_INT_DELTA,
    ENC_INT_RAW,
    ENC_STR_DICT_PLAIN,
    ENC_STR_DICT_RLE,
    ENC_STR_RAW,
    decode_page,
    encode_page,
    parse_page_header,
)


class IntPageTest(unittest.TestCase):
    def test_increasing_ints_use_delta_and_roundtrip(self):
        values = list(range(1000, 1065))
        blob, _ = encode_page("int", values, {})
        header, _ = parse_page_header("int", blob)
        self.assertEqual(header["enc"], ENC_INT_DELTA)
        self.assertEqual(header["nrows"], len(values))
        self.assertEqual(header["min"], 1000)
        self.assertEqual(header["max"], 1064)
        decoded, next_offset = decode_page("int", blob)
        self.assertEqual(decoded, values)
        self.assertEqual(next_offset, len(blob))

    def test_each_page_carries_its_own_frame(self):
        """第二页没有第一页的状态也得单独解得出（帧参照在页内）。"""
        first, state = encode_page("int", list(range(0, 10)), {})
        second, _ = encode_page("int", list(range(10, 20)), state)
        values, _ = decode_page("int", second)
        self.assertEqual(values, list(range(10, 20)))

    def test_random_ints_roundtrip_including_extremes(self):
        values = [0, 1, -1, (1 << 63) - 1, -(1 << 63), 1 << 20, -(1 << 20)]
        blob, _ = encode_page("int", values, {})
        decoded, _ = decode_page("int", blob)
        self.assertEqual(decoded, values)

    def test_extreme_delta_roundtrip(self):
        values = [-(1 << 63), 0, (1 << 63) - 1]
        blob, _ = encode_page("int", values, {})
        decoded, _ = decode_page("int", blob)
        self.assertEqual(decoded, values)

    def test_increasing_int_page_compresses_well(self):
        values = list(range(100_000, 100_000 + 65536))
        blob, _ = encode_page("int", values, {})
        self.assertLess(len(blob), len(values) * 8 * 0.2)


class StrPageTest(unittest.TestCase):
    def test_low_cardinality_run_uses_dict_rle(self):
        values = ["北京"] * 100
        blob, state = encode_page("str", values, {})
        header, _ = parse_page_header("str", blob)
        self.assertEqual(header["enc"], ENC_STR_DICT_RLE)
        self.assertEqual(header["min"], "北京")
        self.assertEqual(header["max"], "北京")
        decoded, _ = decode_page("str", blob)
        self.assertEqual(decoded, values)

    def test_low_cardinality_page_compresses_well(self):
        values = (["北京", "上海", "广州", "深圳"] * 2000)[:65536]
        blob, _ = encode_page("str", values, {})
        raw = sum(1 + len(v.encode("utf-8")) for v in values)
        self.assertLess(len(blob), raw * 0.2)

    def test_distinct_strings_can_fall_back_to_raw(self):
        values = ["v%05d" % index for index in range(50)]
        blob, _ = encode_page("str", values, {})
        decoded, _ = decode_page("str", blob)
        self.assertEqual(decoded, values)

    def test_empty_string_min_max(self):
        values = ["", "abc", ""]
        blob, _ = encode_page("str", values, {})
        header, _ = parse_page_header("str", blob)
        self.assertEqual(header["min"], "")
        self.assertEqual(header["max"], "abc")
        decoded, _ = decode_page("str", blob)
        self.assertEqual(decoded, values)

    def test_dictionary_reused_across_pages_and_old_page_stands_alone(self):
        first, state = encode_page("str", ["北京", "上海"], {})
        second, state = encode_page("str", ["上海", "广州"], state)
        # 第二页字典扩了，但第一页的字节没带新字典也能单独解。
        self.assertEqual(decode_page("str", first)[0], ["北京", "上海"])
        self.assertEqual(decode_page("str", second)[0], ["上海", "广州"])
        # 第三页字典不变，照样自解。
        third, _ = encode_page("str", ["广州", "北京"], state)
        self.assertEqual(decode_page("str", third)[0], ["广州", "北京"])


class CorruptPageTest(unittest.TestCase):
    def test_payload_bit_flap_fails_checksum(self):
        blob, _ = encode_page("int", list(range(50)), {})
        broken = bytearray(blob)
        broken[-10] ^= 0xFF
        with self.assertRaises(BadPageError):
            parse_page_header("int", bytes(broken))

    def test_header_bit_flap_fails_checksum(self):
        blob, _ = encode_page("str", ["a", "b"], {})
        broken = bytearray(blob)
        broken[2] ^= 0x01
        with self.assertRaises(BadPageError):
            decode_page("str", bytes(broken))

    def test_unknown_encoding_rejected(self):
        blob, _ = encode_page("int", [1, 2], {})
        head_len = blob[0]
        broken = bytearray(blob)
        broken[1] = 99
        # 同步修 CRC，让它卡在“编码不认识”而不是校验不过。
        frame_end = len(broken) - 4
        broken[frame_end:frame_end + 4] = struct.pack(
            "<I", zlib.crc32(bytes(broken[:frame_end])) & 0xFFFFFFFF)
        self.assertEqual(head_len, blob[0])
        with self.assertRaises(FormatError):
            decode_page("int", bytes(broken))


class PageEncodingConstantTest(unittest.TestCase):
    def test_encodings_are_distinct(self):
        codes = {ENC_INT_DELTA, ENC_INT_RAW, ENC_STR_DICT_PLAIN,
                 ENC_STR_DICT_RLE, ENC_STR_RAW}
        self.assertEqual(len(codes), 5)


if __name__ == "__main__":
    unittest.main()
