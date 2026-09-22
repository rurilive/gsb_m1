"""Extractor 现有行为的锁定测试：正常包怎么进怎么出。"""

import os
import shutil
import tempfile
import unittest
import zipfile

import support  # noqa: F401  先挂 sys.path

from unseal import KIND_DIR, KIND_HARDLINK, KIND_SYMLINK, Extractor
from unseal.reference import Forged, forge_tar, forge_zip


class ExtractZipTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unseal-extract-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.dest = os.path.join(self.dir, "dest")

    def make_zip(self, items, name="pack.zip"):
        path = os.path.join(self.dir, name)
        forge_zip(path, items)
        return path

    def test_nested_files_land_at_relative_paths(self):
        path = self.make_zip([
            Forged("notes.txt", data=b"top"),
            Forged("docs/guide.txt", data=b"guide"),
            Forged("docs/img/logo.bin", data=b"logo"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual(support.read(self.dest, "notes.txt"), b"top")
        self.assertEqual(support.read(self.dest, "docs/guide.txt"), b"guide")
        self.assertEqual(support.read(self.dest, "docs/img/logo.bin"), b"logo")
        self.assertEqual([item.relpath for item in report.results],
                         ["notes.txt", "docs/guide.txt", "docs/img/logo.bin"])
        self.assertEqual([item.action for item in report.results],
                         ["write", "write", "write"])
        self.assertEqual(report.written, 3)
        self.assertEqual(report.bytes, 3 + 5 + 4)
        self.assertTrue(report.summary().startswith("3 条"))

    def test_dir_entry_makes_directory(self):
        path = self.make_zip([Forged("empty/", kind=KIND_DIR)])
        report = Extractor(self.dest).run(path)
        self.assertTrue(os.path.isdir(os.path.join(self.dest, "empty")))
        self.assertEqual(report.dirs, 1)

    def test_rerun_over_complete_file_skips(self):
        path = self.make_zip([Forged("notes.txt", data=b"top")])
        Extractor(self.dest).run(path)
        before = os.stat(os.path.join(self.dest, "notes.txt"))
        report = Extractor(self.dest).run(path)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.written, 0)
        self.assertEqual(report.results[0].action, "skip")
        self.assertEqual(os.stat(os.path.join(self.dest, "notes.txt")).st_mtime_ns,
                         before.st_mtime_ns)
        self.assertEqual(support.read(self.dest, "notes.txt"), b"top")

    def test_dest_is_created_when_missing(self):
        path = self.make_zip([Forged("a.txt", data=b"a")])
        dest = os.path.join(self.dir, "deep", "nested", "dest")
        Extractor(dest).run(path)
        self.assertEqual(support.read(dest, "a.txt"), b"a")

    def test_empty_archive_reports_nothing(self):
        path = os.path.join(self.dir, "empty.zip")
        with zipfile.ZipFile(path, "w"):
            pass
        report = Extractor(self.dest).run(path)
        self.assertEqual(report.results, [])
        self.assertEqual(report.bytes, 0)
        self.assertTrue(os.path.isdir(self.dest))


class ExtractTarTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unseal-extract-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.dest = os.path.join(self.dir, "dest")

    def test_files_dir_symlink_and_hardlink(self):
        path = os.path.join(self.dir, "pack.tar")
        forge_tar(path, [
            Forged("data/", kind=KIND_DIR),
            Forged("data/real.txt", data=b"payload"),
            Forged("data/soft", kind=KIND_SYMLINK, target="real.txt"),
            Forged("data/hard", kind=KIND_HARDLINK, target="data/real.txt"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual(sorted(support.tree(self.dest)),
                         ["data", "data/hard", "data/real.txt", "data/soft"])
        self.assertEqual(support.tree(self.dest)["data/soft"], "link:real.txt")
        self.assertEqual(support.read(self.dest, "data/real.txt"), b"payload")
        self.assertEqual(support.read(self.dest, "data/hard"), b"payload")
        self.assertEqual(support.read(self.dest, "data/soft"), b"payload")
        self.assertEqual(report.dirs, 1)
        self.assertEqual(report.links, 2)
        self.assertEqual(report.written, 1)


if __name__ == "__main__":
    unittest.main()
