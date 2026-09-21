"""只追加日志：内存版与文件 fsync 版的写入、回放、重开。"""

import os
import tempfile
import unittest

from leasekeeper.journal import FileJournal, MemoryJournal


class MemoryJournalTest(unittest.TestCase):
    def test_append_replay_in_order(self):
        journal = MemoryJournal()
        self.assertEqual(journal.append({"event": "grant", "token": 1}), 0)
        self.assertEqual(journal.append({"event": "deny"}), 1)
        self.assertEqual(
            journal.replay(), [{"event": "grant", "token": 1}, {"event": "deny"}]
        )

    def test_replay_returns_copies(self):
        journal = MemoryJournal()
        journal.append({"event": "grant", "fields": {"token": 1}})
        records = journal.replay()
        records[0]["fields"]["token"] = 99
        self.assertEqual(journal.replay()[0]["fields"]["token"], 1)

    def test_closed_journal_rejects_writes(self):
        journal = MemoryJournal()
        journal.close()
        with self.assertRaises(RuntimeError):
            journal.append({"event": "grant"})


class FileJournalTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix="lk-journal-")
        os.close(fd)
        os.remove(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_append_reopen_replay(self):
        journal = FileJournal(self.path)
        journal.append({"event": "grant", "token": 7, "holder": "n1"})
        journal.append({"event": "release", "lease_id": "L000007"})
        journal.close()
        replayed = FileJournal(self.path)
        records = replayed.replay()
        replayed.close()
        self.assertEqual(records[0]["token"], 7)
        self.assertEqual(records[1]["lease_id"], "L000007")

    def test_seq_continues_after_reopen(self):
        journal = FileJournal(self.path)
        self.assertEqual(journal.append({"event": "grant"}), 0)
        journal.close()
        reopened = FileJournal(self.path)
        self.assertEqual(reopened.append({"event": "grant"}), 1)
        reopened.close()

    def test_unicode_payload_roundtrip(self):
        journal = FileJournal(self.path)
        journal.append({"event": "grant", "resource": "库.主-表"})
        journal.close()
        reopened = FileJournal(self.path)
        self.assertEqual(reopened.replay()[0]["resource"], "库.主-表")
        reopened.close()

    def test_torn_tail_from_crash_is_dropped(self):
        journal = FileJournal(self.path)
        journal.append({"event": "grant", "token": 1})
        journal.close()
        with open(self.path, "a", encoding="utf-8") as source:
            source.write('{"event": "grant", "to')  # 崩在写一半
        reopened = FileJournal(self.path)
        self.assertEqual(len(reopened.replay()), 1)
        # 截掉残尾后还能继续追加，回放仍完整。
        reopened.append({"event": "grant", "token": 2})
        reopened.close()
        self.assertEqual(len(FileJournal(self.path).replay()), 2)

    def test_corrupt_middle_line_raises(self):
        journal = FileJournal(self.path)
        journal.append({"event": "grant", "token": 1})
        journal.close()
        with open(self.path, "a", encoding="utf-8") as source:
            source.write("not-json\n")
            source.write('{"event": "grant", "token": 2}\n')
        with self.assertRaises(ValueError):
            FileJournal(self.path).replay()


if __name__ == "__main__":
    unittest.main()
