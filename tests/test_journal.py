"""Journal 落盘与读回口径的锁定测试。"""

import json
import os
import tempfile
import unittest

from eventwire.journal import Journal


class JournalTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "events.jsonl")

    def open_journal(self):
        journal = Journal(self.path)
        self.addCleanup(journal.close)
        return journal

    def write_raw(self, text):
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(text)


class TestAppend(JournalTest):
    def test_append_writes_one_json_line_per_record(self):
        journal = self.open_journal()
        journal.append({"seq": 1, "topic": "order.created"})
        journal.append({"seq": 2, "topic": "order.paid"})
        with open(self.path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["seq"], 1)
        self.assertEqual(json.loads(lines[1])["topic"], "order.paid")

    def test_records_survive_reopen(self):
        journal = self.open_journal()
        journal.append({"seq": 1, "topic": "tick", "payload": {"n": 1}})
        journal.close()
        reopened = self.open_journal()
        self.assertEqual(
            reopened.read(),
            [{"payload": {"n": 1}, "seq": 1, "topic": "tick"}],
        )

    def test_non_dict_record_rejected(self):
        journal = self.open_journal()
        for bad in ["text", 3, None, ["a"]]:
            with self.assertRaises(TypeError):
                journal.append(bad)

    def test_append_after_close_rejected(self):
        journal = self.open_journal()
        journal.close()
        journal.close()  # 重复关闭没事
        with self.assertRaises(ValueError):
            journal.append({"seq": 1})

    def test_context_manager_closes(self):
        with Journal(self.path) as journal:
            journal.append({"seq": 1})
        with self.assertRaises(ValueError):
            journal.append({"seq": 2})


class TestRead(JournalTest):
    def test_empty_file_reads_empty(self):
        self.assertEqual(self.open_journal().read(), [])

    def test_order_kept(self):
        journal = self.open_journal()
        for seq in range(1, 5):
            journal.append({"seq": seq})
        self.assertEqual([r["seq"] for r in journal.read()], [1, 2, 3, 4])

    def test_blank_lines_skipped(self):
        journal = self.open_journal()
        journal.append({"seq": 1})
        self.write_raw("\n   \n")
        journal.append({"seq": 2})
        self.assertEqual([r["seq"] for r in journal.read()], [1, 2])

    def test_torn_tail_ignored(self):
        journal = self.open_journal()
        journal.append({"seq": 1})
        self.write_raw('{"seq": 2, "top')  # 写一半就被杀的现场
        self.assertEqual([r["seq"] for r in journal.read()], [1])

    def test_complete_tail_without_newline_kept(self):
        self.write_raw('{"seq": 1}\n{"seq": 2}')
        self.assertEqual([r["seq"] for r in self.open_journal().read()], [1, 2])

    def test_corrupt_middle_line_raises(self):
        journal = self.open_journal()
        journal.append({"seq": 1})
        self.write_raw("{broken}\n")
        journal.append({"seq": 3})
        with self.assertRaises(ValueError):
            journal.read()

    def test_non_object_line_raises(self):
        self.write_raw("[1, 2]\n")
        with self.assertRaises(ValueError):
            self.open_journal().read()

    def test_read_after_close_still_works(self):
        journal = self.open_journal()
        journal.append({"seq": 1})
        journal.close()
        self.assertEqual(journal.read(), [{"seq": 1}])


class TestTruncate(JournalTest):
    def test_truncate_clears_file_and_keeps_appending(self):
        journal = self.open_journal()
        journal.append({"seq": 1})
        journal.append({"seq": 2})
        journal.truncate()
        self.assertEqual(journal.read(), [])
        journal.append({"seq": 9})
        self.assertEqual(journal.read(), [{"seq": 9}])

    def test_invalid_path_rejected(self):
        with self.assertRaises(ValueError):
            Journal("")


if __name__ == "__main__":
    unittest.main()
