"""朴素全量哈希的锁定测试。

只覆盖当前实现已经具备的能力：对字节与文本求 SHA-256、把整份列表
串起来求一次根指纹、确定性与空列表语义。新增能力（分层建树、增量
更新、包含证明、范围证明、根一致性、顺序无关）另开测试文件，本文件
一字不改。
"""

import hashlib
import unittest

from merkletool.hash import hash_bytes, hash_text, naive_root


class TestHashBytesAndText(unittest.TestCase):
    def test_hash_bytes_matches_sha256(self):
        self.assertEqual(
            hash_bytes(b"hello"),
            hashlib.sha256(b"hello").hexdigest(),
        )

    def test_hash_bytes_is_lower_hex_of_64(self):
        digest = hash_bytes(b"anything")
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.lower())
        int(digest, 16)

    def test_hash_text_uses_utf8(self):
        self.assertEqual(
            hash_text("abc"),
            hash_bytes("abc".encode("utf-8")),
        )

    def test_hash_text_handles_non_ascii(self):
        self.assertEqual(
            hash_text("树"),
            hashlib.sha256("树".encode("utf-8")).hexdigest(),
        )

    def test_hash_bytes_rejects_text(self):
        with self.assertRaises(TypeError):
            hash_bytes("not bytes")

    def test_hash_text_rejects_bytes(self):
        with self.assertRaises(TypeError):
            hash_text(b"not text")


class TestNaiveRoot(unittest.TestCase):
    def test_root_is_sha256_of_concatenated_leaves(self):
        leaves = ["a", "b", "c"]
        expected = hashlib.sha256(b"abc").hexdigest()
        self.assertEqual(naive_root(leaves), expected)

    def test_empty_list_hashes_empty_concatenation(self):
        self.assertEqual(
            naive_root([]),
            hashlib.sha256(b"").hexdigest(),
        )

    def test_root_is_deterministic(self):
        leaves = ["x", "y", "z"]
        self.assertEqual(naive_root(leaves), naive_root(leaves))

    def test_str_and_bytes_leaves_agree(self):
        self.assertEqual(
            naive_root(["a", "b"]),
            naive_root([b"a", b"b"]),
        )

    def test_any_leaf_change_changes_root(self):
        base = naive_root(["a", "b", "c"])
        self.assertNotEqual(base, naive_root(["a", "B", "c"]))

    def test_naive_root_depends_on_order(self):
        self.assertNotEqual(
            naive_root(["a", "b"]),
            naive_root(["b", "a"]),
        )

    def test_leaf_must_be_str_or_bytes(self):
        with self.assertRaises(TypeError):
            naive_root([1, 2, 3])


if __name__ == "__main__":
    unittest.main()
