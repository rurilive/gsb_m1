"""hashing 模块现有行为的锁定测试。"""

import hashlib
import os
import tempfile
import unittest

from snapwire.hashing import hash_bytes, hash_file

EMPTY_SHA256 = ("e3b0c44298fc1c149afbf4c8996fb924"
                "27ae41e4649b934ca495991b7852b855")
ABC_SHA256 = ("ba7816bf8f01cfea414140de5dae2223"
              "b00361a396177a9cb410ff61f20015ad")


class TestHashBytes(unittest.TestCase):
    def test_known_digests(self):
        self.assertEqual(hash_bytes(b""), EMPTY_SHA256)
        self.assertEqual(hash_bytes(b"abc"), ABC_SHA256)

    def test_matches_hashlib(self):
        data = os.urandom(4096)
        self.assertEqual(hash_bytes(data), hashlib.sha256(data).hexdigest())


class TestHashFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write(self, name, data):
        path = self.path(name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_empty_file(self):
        path = self.write("empty.bin", b"")
        self.assertEqual(hash_file(path), EMPTY_SHA256)

    def test_small_file(self):
        path = self.write("abc.bin", b"abc")
        self.assertEqual(hash_file(path), ABC_SHA256)

    def test_binary_file(self):
        data = bytes(range(256)) * 64 + b"\x00\xff" * 3
        path = self.write("blob.bin", data)
        self.assertEqual(hash_file(path), hash_bytes(data))

    def test_chunk_size_does_not_change_digest(self):
        data = os.urandom(5000)
        path = self.write("data.bin", data)
        reference = hash_bytes(data)
        for chunk_size in (1, 7, 999, 5000, 1 << 20):
            self.assertEqual(hash_file(path, chunk_size=chunk_size), reference)

    def test_non_positive_chunk_size_raises(self):
        path = self.write("x.bin", b"x")
        for chunk_size in (0, -1):
            with self.assertRaises(ValueError):
                hash_file(path, chunk_size=chunk_size)


if __name__ == "__main__":
    unittest.main()
