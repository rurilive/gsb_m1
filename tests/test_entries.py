"""条目的归一：zip 与 tar 读出来得是同一套 Entry。"""

import io
import os
import shutil
import tarfile
import tempfile
import unittest

import support  # noqa: F401  先挂 sys.path

from unseal import (
    KIND_DIR,
    KIND_FILE,
    KIND_HARDLINK,
    KIND_SYMLINK,
    ArchiveError,
    iter_archive,
)
from unseal.reference import Forged, forge_tar, forge_zip


class ZipEntriesTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unseal-entries-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_zip_file_dir_and_symlink(self):
        path = os.path.join(self.dir, "pack.zip")
        forge_zip(path, [
            Forged("docs/", kind=KIND_DIR),
            Forged("docs/readme.txt", data=b"hello"),
            Forged("docs/current", kind=KIND_SYMLINK, target="readme.txt"),
        ])
        entries = list(iter_archive(path))
        self.assertEqual([entry.name for entry in entries],
                         ["docs/", "docs/readme.txt", "docs/current"])
        self.assertEqual([entry.kind for entry in entries],
                         [KIND_DIR, KIND_FILE, KIND_SYMLINK])
        self.assertEqual(entries[1].declared_size, 5)
        self.assertEqual(entries[2].linkname, "readme.txt")
        self.assertEqual(entries[1].open().read(), b"hello")

    def test_tar_file_dir_and_links(self):
        path = os.path.join(self.dir, "pack.tar")
        forge_tar(path, [
            Forged("data/", kind=KIND_DIR),
            Forged("data/real.txt", data=b"payload"),
            Forged("data/soft", kind=KIND_SYMLINK, target="real.txt"),
            Forged("data/hard", kind=KIND_HARDLINK, target="data/real.txt"),
        ])
        entries = list(iter_archive(path))
        self.assertEqual([entry.kind for entry in entries],
                         [KIND_DIR, KIND_FILE, KIND_SYMLINK, KIND_HARDLINK])
        self.assertEqual(entries[1].declared_size, 7)
        self.assertEqual(entries[2].linkname, "real.txt")
        self.assertEqual(entries[3].linkname, "data/real.txt")

    def test_unknown_tar_member_comes_back_as_other(self):
        path = os.path.join(self.dir, "odd.tar")
        with tarfile.open(path, "w") as archive:
            info = tarfile.TarInfo("pipe")
            info.type = tarfile.FIFOTYPE
            archive.addfile(info)
            payload = tarfile.TarInfo("keep.txt")
            payload.size = 2
            archive.addfile(payload, io.BytesIO(b"ok"))
        entries = list(iter_archive(path))
        self.assertEqual(entries[0].kind, "other")
        self.assertEqual(entries[1].kind, KIND_FILE)

    def test_unknown_format_is_rejected(self):
        path = os.path.join(self.dir, "notes.txt")
        with open(path, "wb") as handle:
            handle.write(b"just some text, not an archive\n")
        with self.assertRaises(ArchiveError):
            list(iter_archive(path))


if __name__ == "__main__":
    unittest.main()
