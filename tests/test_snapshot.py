"""snapshot 模块现有行为的锁定测试。"""

import json
import os
import tempfile
import unittest

from snapwire.hashing import hash_bytes
from snapwire.snapshot import (
    Change,
    Entry,
    Snapshot,
    compare_snapshots,
    load_snapshot,
    save_snapshot,
    take_snapshot,
)


class SnapshotFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def write(self, rel, data):
        path = os.path.join(self.root, rel)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return path


class TestTakeSnapshot(SnapshotFixture):
    def test_entries_record_size_and_digest(self):
        self.write("a.txt", b"abc")
        self.write("sub/b.bin", b"\x00\x01")
        snap = take_snapshot(self.root)
        self.assertEqual(len(snap), 2)
        self.assertEqual(
            snap.entries["a.txt"],
            Entry(size=3, digest=hash_bytes(b"abc")))
        self.assertEqual(
            snap.entries["sub/b.bin"],
            Entry(size=2, digest=hash_bytes(b"\x00\x01")))

    def test_paths_use_slashes_and_sorted(self):
        self.write("z.txt", b"z")
        self.write("a/b/c.txt", b"c")
        snap = take_snapshot(self.root)
        self.assertEqual(snap.paths(), ["a/b/c.txt", "z.txt"])

    def test_dot_entries_are_skipped(self):
        self.write("keep.txt", b"k")
        self.write(".hidden", b"h")
        self.write(".cache/blob", b"b")
        snap = take_snapshot(self.root)
        self.assertEqual(snap.paths(), ["keep.txt"])

    def test_empty_dir_gives_empty_snapshot(self):
        snap = take_snapshot(self.root)
        self.assertEqual(len(snap), 0)
        self.assertEqual(snap.paths(), [])

    def test_empty_file_entry(self):
        self.write("empty.bin", b"")
        snap = take_snapshot(self.root)
        self.assertEqual(snap.entries["empty.bin"].size, 0)
        self.assertEqual(snap.entries["empty.bin"].digest, hash_bytes(b""))


class TestCompareSnapshots(SnapshotFixture):
    def test_classifies_added_removed_modified(self):
        self.write("stays.txt", b"same")
        self.write("gone.txt", b"bye")
        self.write("touched.txt", b"old")
        before = take_snapshot(self.root)

        self.write("touched.txt", b"new")
        os.remove(os.path.join(self.root, "gone.txt"))
        self.write("fresh.txt", b"hi")
        after = take_snapshot(self.root)

        self.assertEqual(
            compare_snapshots(before, after),
            [Change("added", "fresh.txt"),
             Change("removed", "gone.txt"),
             Change("modified", "touched.txt")])

    def test_identical_content_is_not_a_change(self):
        path = self.write("a.txt", b"same bytes")
        before = take_snapshot(self.root)
        os.utime(path, (1, 1))
        self.write("a.txt", b"same bytes")
        after = take_snapshot(self.root)
        self.assertEqual(compare_snapshots(before, after), [])

    def test_identical_snapshots_compare_empty(self):
        self.write("a.txt", b"a")
        snap = take_snapshot(self.root)
        self.assertEqual(compare_snapshots(snap, snap), [])

    def test_change_is_a_frozen_record(self):
        change = Change("added", "x")
        with self.assertRaises(AttributeError):
            change.kind = "removed"


class TestSnapshotStore(SnapshotFixture):
    def test_roundtrip(self):
        self.write("a.txt", b"abc")
        self.write("d/b.bin", b"\x00")
        snap = take_snapshot(self.root)
        out = os.path.join(self.root, "nested", "snap.json")
        save_snapshot(snap, out)
        loaded = load_snapshot(out)
        self.assertEqual(loaded.paths(), snap.paths())
        self.assertEqual(loaded.entries, snap.entries)
        self.assertEqual(loaded, snap)

    def test_saved_file_is_json_with_version(self):
        snap = take_snapshot(self.root)
        out = os.path.join(self.root, "snap.json")
        save_snapshot(snap, out)
        with open(out, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["entries"], {})

    def test_unknown_version_raises(self):
        out = os.path.join(self.root, "snap.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"version": 99, "root": self.root, "entries": {}}, fh)
        with self.assertRaises(ValueError):
            load_snapshot(out)


class TestSnapshotObject(unittest.TestCase):
    def test_len_contains_and_repr(self):
        snap = Snapshot("/x", {"a": Entry(1, "d")})
        self.assertEqual(len(snap), 1)
        self.assertIn("a", snap)
        self.assertNotIn("b", snap)
        self.assertIn("entries=1", repr(snap))


if __name__ == "__main__":
    unittest.main()
