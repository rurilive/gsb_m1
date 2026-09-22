"""性能基线：十万小文件解压，三分钟封顶；重跑全跳过也不许更慢。"""

import os
import shutil
import tempfile
import time
import unittest
import zipfile

import support  # noqa: F401  先挂 sys.path

from unseal import Extractor

FILE_COUNT = 100000
TIME_BUDGET = 180.0


class SmallFilesPerfTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unseal-perf-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def make_archive(self):
        path = os.path.join(self.dir, "big.zip")
        payload = b"x" * 32
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
            for index in range(FILE_COUNT):
                archive.writestr("d%03d/f%05d.txt" % (index % 200, index),
                                 payload)
        return path

    def test_hundred_k_small_files_within_budget(self):
        path = self.make_archive()
        dest = os.path.join(self.dir, "dest")
        start = time.monotonic()
        report = Extractor(dest).run(path)
        elapsed = time.monotonic() - start
        self.assertEqual(report.written, FILE_COUNT)
        self.assertEqual(report.rejected, 0)
        self.assertLess(elapsed, TIME_BUDGET,
                        "解压 %d 个文件耗时 %.1fs，超预算" % (FILE_COUNT,
                                                           elapsed))
        start = time.monotonic()
        rerun = Extractor(dest).run(path)
        elapsed = time.monotonic() - start
        self.assertEqual(rerun.skipped, FILE_COUNT)
        self.assertLess(elapsed, TIME_BUDGET,
                        "重跑跳过 %d 个文件耗时 %.1fs，超预算" % (FILE_COUNT,
                                                               elapsed))


if __name__ == "__main__":
    unittest.main()
