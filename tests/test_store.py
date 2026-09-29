"""MemStore 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：扁平键到字节串的读写、追加、删除、
按字典序列出键、缺失键的错误、非法入参的构造期拒绝，以及 in 与 len。
新增行为（目录树、路径解析、符号链接、硬链接、配额）另建测试文件，
不改动本文件。
"""

import unittest

from memfs.store import MemStore


class TestWriteRead(unittest.TestCase):
    def test_write_then_read(self):
        s = MemStore()
        self.assertEqual(s.write("a", b"hello"), 5)
        self.assertEqual(s.read("a"), b"hello")

    def test_write_overwrites(self):
        s = MemStore()
        s.write("a", b"longer")
        s.write("a", b"x")
        self.assertEqual(s.read("a"), b"x")
        self.assertEqual(s.size("a"), 1)

    def test_write_returns_byte_count(self):
        s = MemStore()
        self.assertEqual(s.write("k", b"\x00\x01\x02"), 3)

    def test_write_accepts_bytearray(self):
        s = MemStore()
        s.write("a", bytearray(b"abc"))
        self.assertEqual(s.read("a"), b"abc")

    def test_read_missing_raises(self):
        s = MemStore()
        with self.assertRaises(KeyError):
            s.read("absent")


class TestAppend(unittest.TestCase):
    def test_append_to_existing(self):
        s = MemStore()
        s.write("a", b"foo")
        self.assertEqual(s.append("a", b"bar"), 6)
        self.assertEqual(s.read("a"), b"foobar")

    def test_append_creates_missing(self):
        s = MemStore()
        self.assertEqual(s.append("a", b"z"), 1)
        self.assertEqual(s.read("a"), b"z")


class TestRemoveAndSize(unittest.TestCase):
    def test_remove_existing_returns_true(self):
        s = MemStore()
        s.write("a", b"x")
        self.assertTrue(s.remove("a"))
        self.assertNotIn("a", s)

    def test_remove_missing_returns_false(self):
        s = MemStore()
        self.assertFalse(s.remove("nope"))

    def test_size(self):
        s = MemStore()
        s.write("a", b"abcd")
        self.assertEqual(s.size("a"), 4)

    def test_size_missing_raises(self):
        s = MemStore()
        with self.assertRaises(KeyError):
            s.size("absent")


class TestKeysAndLen(unittest.TestCase):
    def test_keys_sorted(self):
        s = MemStore()
        s.write("b", b"1")
        s.write("a", b"2")
        s.write("c", b"3")
        self.assertEqual(s.keys(), ["a", "b", "c"])

    def test_contains_and_len(self):
        s = MemStore()
        s.write("a", b"1")
        s.write("b", b"2")
        self.assertIn("a", s)
        self.assertNotIn("z", s)
        self.assertEqual(len(s), 2)

    def test_clear(self):
        s = MemStore()
        s.write("a", b"1")
        s.clear()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.keys(), [])


class TestGuards(unittest.TestCase):
    def test_empty_key_rejected(self):
        s = MemStore()
        with self.assertRaises(ValueError):
            s.write("", b"x")

    def test_non_str_key_rejected(self):
        s = MemStore()
        with self.assertRaises(ValueError):
            s.write(3, b"x")

    def test_non_bytes_data_rejected(self):
        s = MemStore()
        with self.assertRaises(TypeError):
            s.write("a", "text")


if __name__ == "__main__":
    unittest.main()
