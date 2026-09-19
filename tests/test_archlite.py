"""archlite 行为清单——重构期间一个字都不改，必须原样全绿。"""

import os
import struct
import tempfile
import unittest

from archlite import (
    ArchiveEntry,
    find_entry,
    pack_bytes,
    read_archive,
    unpack_bytes,
    write_archive,
)

# 单条目 ("a.txt", b"hi") 的逐字节黄金样本（头 512 + 数据补零 512 + 结束块 1024）
GOLDEN_A = (
    b"ARCL" + b"a.txt" + b"\x00" * 59
    + b"\x00\x00\x00\x00\x00\x00\x00\x02"
    + b"\x00\x00\x03\x13"
    + b"\x00" * 432
    + b"hi" + b"\x00" * 510
    + b"\x00" * 1024
)


def craft_header(name_bytes, size):
    """测试侧手工造一个校验和正确的头。"""
    head = bytearray(512)
    head[0:4] = b"ARCL"
    head[4:4 + len(name_bytes)] = name_bytes
    head[68:76] = struct.pack(">Q", size)
    chk = sum(head) & 0xFFFFFFFF
    head[76:80] = struct.pack(">I", chk)
    return bytes(head)


class TestPackGolden(unittest.TestCase):
    def test_golden_bytes(self):
        blob = pack_bytes([ArchiveEntry("a.txt", b"hi")])
        self.assertEqual(blob, GOLDEN_A)
        self.assertEqual(len(blob), 2048)

    def test_empty_archive(self):
        self.assertEqual(pack_bytes([]), b"\x00" * 1024)

    def test_pack_deterministic(self):
        entries = [ArchiveEntry("x", b"1"), ArchiveEntry("y", b"22")]
        self.assertEqual(pack_bytes(entries), pack_bytes(list(entries)))

    def test_data_size_zero(self):
        blob = pack_bytes([ArchiveEntry("m", b"")])
        self.assertEqual(len(blob), 1536)
        self.assertEqual(unpack_bytes(blob), [ArchiveEntry("m", b"")])

    def test_data_size_512(self):
        blob = pack_bytes([ArchiveEntry("m", b"z" * 512)])
        self.assertEqual(len(blob), 2048)
        self.assertEqual(unpack_bytes(blob), [ArchiveEntry("m", b"z" * 512)])

    def test_data_size_513(self):
        blob = pack_bytes([ArchiveEntry("m", b"z" * 513)])
        self.assertEqual(len(blob), 512 + 1024 + 1024)
        self.assertEqual(unpack_bytes(blob), [ArchiveEntry("m", b"z" * 513)])


class TestRoundtrip(unittest.TestCase):
    def test_simple(self):
        e = ArchiveEntry("dir/file.txt", b"hello world")
        self.assertEqual(unpack_bytes(pack_bytes([e])), [e])

    def test_multi_with_empty(self):
        entries = [
            ArchiveEntry("a", b""),
            ArchiveEntry("b/c", b"data"),
            ArchiveEntry("d", b"\x00\xff"),
        ]
        self.assertEqual(unpack_bytes(pack_bytes(entries)), entries)

    def test_binary_all_bytes(self):
        e = ArchiveEntry("blob", bytes(range(256)) * 4)
        self.assertEqual(unpack_bytes(pack_bytes([e])), [e])

    def test_unicode_name(self):
        e = ArchiveEntry("配置/说明.txt", b"ok")
        self.assertEqual(unpack_bytes(pack_bytes([e])), [e])

    def test_order_and_duplicates_preserved(self):
        entries = [ArchiveEntry("same", b"first"), ArchiveEntry("same", b"second")]
        out = unpack_bytes(pack_bytes(entries))
        self.assertEqual(out, entries)
        self.assertEqual(out[0].data, b"first")

    def test_unpack_then_pack_identical(self):
        entries = [ArchiveEntry("a", b"1" * 700), ArchiveEntry("b", b"")]
        blob = pack_bytes(entries)
        self.assertEqual(pack_bytes(unpack_bytes(blob)), blob)


class TestUnpackErrors(unittest.TestCase):
    def test_truncated_empty(self):
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(b"")
        self.assertEqual(str(cm.exception), "truncated header: got 0 bytes")

    def test_truncated_partial(self):
        for n in [2, 100, 511]:
            with self.assertRaises(ValueError) as cm:
                unpack_bytes((b"ARCL" + b"\x01" * n)[:n])
            self.assertEqual(str(cm.exception), "truncated header: got %d bytes" % n)

    def test_bad_magic(self):
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(b"XXXX" + b"\x00" * 508)
        self.assertEqual(str(cm.exception), "not an archlite archive: magic=b'XXXX'")

    def test_checksum_mismatch_first(self):
        blob = pack_bytes([ArchiveEntry("a.txt", b"hi")])
        bad = blob[:10] + bytes([blob[10] ^ 0xFF]) + blob[11:]
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(bad)
        self.assertEqual(str(cm.exception), "header checksum mismatch at entry 0")

    def test_checksum_mismatch_second(self):
        blob = pack_bytes([ArchiveEntry("a", b"1"), ArchiveEntry("b", b"2")])
        pos = 1024 + 10
        bad = blob[:pos] + bytes([blob[pos] ^ 0xFF]) + blob[pos + 1:]
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(bad)
        self.assertEqual(str(cm.exception), "header checksum mismatch at entry 1")

    def test_magic_checked_before_checksum(self):
        blob = pack_bytes([ArchiveEntry("a", b"1")])
        bad = b"XXXX" + blob[4:]
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(bad)
        self.assertEqual(str(cm.exception), "not an archlite archive: magic=b'XXXX'")

    def test_truncated_data(self):
        blob = pack_bytes([ArchiveEntry("a.txt", b"hi")])
        cut = blob[:512 + 600]
        # 手工把头里的长度改成 1000（校验和同步重算），数据只剩 600
        head = bytearray(cut[:512])
        head[68:76] = struct.pack(">Q", 1000)
        chk = (sum(head[:76]) + sum(head[80:])) & 0xFFFFFFFF
        head[76:80] = struct.pack(">I", chk)
        bad = bytes(head) + cut[512:]
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(bad)
        self.assertEqual(
            str(cm.exception), "truncated data for 'a.txt': expected 1000 bytes, got 600"
        )

    def test_tail_short_bytes_ignored(self):
        blob = pack_bytes([ArchiveEntry("a", b"x")]) + b"junkjunk"
        self.assertEqual(unpack_bytes(blob), [ArchiveEntry("a", b"x")])

    def test_single_zero_block_is_end(self):
        self.assertEqual(unpack_bytes(b"\x00" * 512), [])

    def test_missing_end_block_tolerated(self):
        blob = pack_bytes([ArchiveEntry("a", b"x")])[:-1024]
        self.assertEqual(unpack_bytes(blob), [ArchiveEntry("a", b"x")])

    def test_junk_block_where_header_expected(self):
        blob = pack_bytes([ArchiveEntry("a", b"x")])[:-1024] + b"junk" * 128
        with self.assertRaises(ValueError) as cm:
            unpack_bytes(blob)
        self.assertEqual(str(cm.exception), "not an archlite archive: magic=b'junk'")

    def test_bad_name_encoding(self):
        blob = craft_header(b"\xff\xfe\xfd", 0) + b"\x00" * 1024
        with self.assertRaises(UnicodeDecodeError):
            unpack_bytes(blob)

    def test_type_error(self):
        with self.assertRaises(TypeError) as cm:
            unpack_bytes("nope")
        self.assertEqual(str(cm.exception), "expected bytes")


class TestFindEntry(unittest.TestCase):
    def setUp(self):
        self.blob = pack_bytes([ArchiveEntry("a", b"1"), ArchiveEntry("b", b"22")])

    def test_found(self):
        self.assertEqual(find_entry(self.blob, "b"), ArchiveEntry("b", b"22"))

    def test_absent(self):
        self.assertIsNone(find_entry(self.blob, "zzz"))

    def test_duplicate_returns_first(self):
        blob = pack_bytes([ArchiveEntry("a", b"1"), ArchiveEntry("a", b"2")])
        self.assertEqual(find_entry(blob, "a").data, b"1")

    def test_corrupt_returns_none(self):
        bad = self.blob[:1034] + bytes([self.blob[1034] ^ 0xFF]) + self.blob[1035:]
        self.assertIsNone(find_entry(bad, "a"))


class TestFileIO(unittest.TestCase):
    def setUp(self):
        self.entries = [
            ArchiveEntry("etc/gw.conf", b"port = 8080\n"),
            ArchiveEntry("empty.marker", b""),
            ArchiveEntry("rand", bytes(range(256)) * 2),
        ]

    def test_write_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.al")
            write_archive(p, self.entries)
            self.assertEqual(read_archive(p), self.entries)

    def test_file_matches_pack(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.al")
            write_archive(p, self.entries)
            with open(p, "rb") as f:
                self.assertEqual(f.read(), pack_bytes(self.entries))

    def test_read_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            read_archive("/nonexistent/gsb-no-such.al")

    def test_read_bad_magic(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bad.al")
            with open(p, "wb") as f:
                f.write(b"XXXX" + b"\x00" * 508)
            with self.assertRaises(ValueError) as cm:
                read_archive(p)
            self.assertEqual(str(cm.exception), "not an archlite archive: magic=b'XXXX'")


class TestEntryAndValidation(unittest.TestCase):
    def test_entry_attrs_eq_repr(self):
        e = ArchiveEntry("a", b"ab")
        self.assertEqual(e.name, "a")
        self.assertEqual(e.data, b"ab")
        self.assertEqual(e, ArchiveEntry("a", b"ab"))
        self.assertNotEqual(e, ArchiveEntry("a", b"xx"))
        self.assertNotEqual(e, "a")
        self.assertEqual(repr(e), "ArchiveEntry(name='a', data=2 bytes)")

    def test_entry_type_errors(self):
        with self.assertRaises(TypeError) as cm:
            ArchiveEntry(5, b"")
        self.assertEqual(str(cm.exception), "entry name must be str")
        with self.assertRaises(TypeError) as cm:
            ArchiveEntry("a", "str")
        self.assertEqual(str(cm.exception), "entry data must be bytes")

    def test_pack_empty_name(self):
        with self.assertRaises(ValueError) as cm:
            pack_bytes([ArchiveEntry("", b"")])
        self.assertEqual(str(cm.exception), "entry name must not be empty")

    def test_pack_name_length_boundary(self):
        pack_bytes([ArchiveEntry("a" * 64, b"")])
        with self.assertRaises(ValueError) as cm:
            pack_bytes([ArchiveEntry("a" * 65, b"")])
        self.assertEqual(str(cm.exception), "entry name too long: 65 > 64 bytes")

    def test_pack_name_nul(self):
        with self.assertRaises(ValueError) as cm:
            pack_bytes([ArchiveEntry("a\x00b", b"")])
        self.assertEqual(str(cm.exception), "entry name must not contain NUL")

    def test_pack_name_counts_utf8_bytes(self):
        pack_bytes([ArchiveEntry("中" * 21, b"")])
        with self.assertRaises(ValueError) as cm:
            pack_bytes([ArchiveEntry("中" * 22, b"")])
        self.assertEqual(str(cm.exception), "entry name too long: 66 > 64 bytes")

    def test_pack_rejects_non_entry(self):
        with self.assertRaises(TypeError) as cm:
            pack_bytes([("a", b"b")])
        self.assertEqual(str(cm.exception), "expected ArchiveEntry, got tuple")


if __name__ == "__main__":
    unittest.main()
