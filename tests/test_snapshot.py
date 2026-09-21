"""PollScanner 与 Snapshot 现有行为的锁定测试。"""

import hashlib
import os
import tempfile
import unittest

from snapwatch import PollScanner, SysFS


def make_file(root, rel, data):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        make_file(self.root, "a.txt", b"hello world")
        make_file(self.root, "d/b.txt", b"")

    def scan(self, fs=None):
        return PollScanner(fs if fs is not None else SysFS(),
                           self.root).scan()

    def test_entries_cover_the_tree(self):
        snap = self.scan()
        self.assertEqual(snap.paths(), ["a.txt", "d", "d/b.txt"])
        self.assertEqual(len(snap), 3)
        self.assertFalse(snap.entry("a.txt").is_dir)
        self.assertTrue(snap.entry("d").is_dir)
        self.assertEqual(snap.entry("a.txt").size, 11)
        self.assertEqual(snap.entry("d/b.txt").size, 0)

    def test_root_is_not_an_entry(self):
        self.assertNotIn("", self.scan().paths())

    def test_digest_is_content_hash(self):
        snap = self.scan()
        self.assertEqual(snap.entry("a.txt").digest,
                         hashlib.sha256(b"hello world").hexdigest())
        self.assertIsNone(snap.entry("d").digest)

    def test_unknown_path_raises(self):
        with self.assertRaises(KeyError):
            self.scan().entry("nope")

    def test_unstattable_child_is_skipped(self):
        class Vanishing(SysFS):
            def stat(self, path):
                if path.endswith("b.txt"):
                    raise FileNotFoundError(path)
                return super().stat(path)

        self.assertEqual(self.scan(Vanishing()).paths(), ["a.txt", "d"])

    def test_unreadable_directory_is_not_fatal(self):
        class Grumpy(SysFS):
            def scandir(self, path):
                if path.endswith(os.sep + "d"):
                    raise PermissionError(path)
                return super().scandir(path)

        self.assertEqual(self.scan(Grumpy()).paths(), ["a.txt", "d"])


if __name__ == "__main__":
    unittest.main()
