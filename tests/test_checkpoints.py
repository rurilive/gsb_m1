"""检查点旁路文件的测试。"""

import os
import shutil
import tempfile
import unittest

from auditchain.checkpoints import CheckpointStore


class CheckpointTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-ckpt-")
        self.path = os.path.join(self.tmpdir, "audit.log.ckpt")
        self.store = CheckpointStore(self.path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_raw(self, blob):
        with open(self.path, "ab") as handle:
            handle.write(blob)


class TestCheckpointAppendLoad(CheckpointTestBase):
    def test_missing_file_loads_empty(self):
        self.assertEqual(self.store.load(), [])
        self.assertFalse(self.store.exists())

    def test_anchors_round_trip_in_order(self):
        self.store.append(100, "a" * 64, "b" * 64, 1200)
        self.store.append(200, "c" * 64, "d" * 64, 2400)
        anchors = self.store.load()
        self.assertEqual([anchor["seq"] for anchor in anchors], [100, 200])
        self.assertEqual(anchors[0]["digest"], "a" * 64)
        self.assertEqual(anchors[0]["prev"], "b" * 64)
        self.assertEqual(anchors[0]["offset"], 1200)
        self.assertTrue(self.store.exists())

    def test_bad_lines_are_skipped_not_fatal(self):
        self.store.append(100, "a" * 64, "b" * 64, 0)
        self.write_raw(b"garbage\n")
        self.write_raw(b'{"seq":200}\n')
        self.write_raw(b'{"seq":-1,"digest":"%s","prev":"","offset":0}\n' % (b"a" * 64))
        self.write_raw(b'{"seq":300,"digest":"%s","prev":"","offset":0}\n' % (b"c" * 64))
        anchors = self.store.load()
        self.assertEqual([anchor["seq"] for anchor in anchors], [100, 300])


class TestCheckpointRewrite(CheckpointTestBase):
    def test_rewrite_replaces_all_anchors(self):
        self.store.append(100, "a" * 64, "b" * 64, 0)
        self.store.rewrite(
            [
                {"seq": 200, "digest": "c" * 64, "prev": "", "offset": 1},
                {"seq": 300, "digest": "d" * 64, "prev": "e" * 64, "offset": 2},
            ]
        )
        self.assertEqual([a["seq"] for a in self.store.load()], [200, 300])

    def test_rewrite_with_nothing_deletes_the_file(self):
        self.store.append(100, "a" * 64, "b" * 64, 0)
        self.store.rewrite([])
        self.assertFalse(self.store.exists())
        self.assertEqual(self.store.load(), [])


if __name__ == "__main__":
    unittest.main()
