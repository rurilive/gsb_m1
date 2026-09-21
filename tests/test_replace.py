"""RecordStore 整文件原子替换的测试（老日志补链用）。"""

import os
import shutil
import tempfile
import unittest

from auditchain.store import RecordStore


class TestReplace(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-replace-")
        self.path = os.path.join(self.tmpdir, "audit.log")
        self.store = RecordStore(self.path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_replace_rewrites_the_whole_file(self):
        self.store.append({"seq": 1})
        self.store.append({"seq": 2})
        size = self.store.replace(
            [
                {"seq": 1, "prev": "", "digest": "a"},
                {"seq": 2, "prev": "a", "digest": "b"},
            ]
        )
        entries, valid_end = self.store.scan()
        self.assertEqual([record["seq"] for _, record in entries], [1, 2])
        self.assertEqual(entries[1][1]["prev"], "a")
        self.assertEqual(valid_end, size)
        self.assertEqual(self.store.size(), size)

    def test_replace_leaves_no_temp_file(self):
        self.store.append({"seq": 1})
        self.store.replace([{"seq": 1, "prev": "", "digest": "a"}])
        leftovers = [name for name in os.listdir(self.tmpdir) if name.endswith(".tmp")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
