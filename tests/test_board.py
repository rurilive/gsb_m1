"""状态板的锁定测试。"""

import unittest

from healthd import StatusBoard


class TestStatusBoard(unittest.TestCase):
    def test_record_and_result(self):
        b = StatusBoard()
        self.assertIsNone(b.result("db"))
        b.record("db", True, "primary")
        r = b.result("db")
        self.assertEqual(r.name, "db")
        self.assertTrue(r.ok)
        self.assertEqual(r.detail, "primary")

    def test_record_overwrites(self):
        b = StatusBoard()
        b.record("db", False, "down")
        b.record("db", True, "back")
        self.assertTrue(b.result("db").ok)
        self.assertEqual(b.result("db").detail, "back")

    def test_snapshot_is_copy(self):
        b = StatusBoard()
        b.record("q", True)
        snap = b.snapshot()
        snap["injected"] = None
        self.assertIsNone(b.result("injected"))
        self.assertEqual(set(b.snapshot()), {"q"})

    def test_overall_no_records_false(self):
        self.assertFalse(StatusBoard().overall_ok())

    def test_overall_all_must_pass(self):
        b = StatusBoard()
        b.record("a", True)
        b.record("b", False)
        self.assertFalse(b.overall_ok())
        b.record("b", True)
        self.assertTrue(b.overall_ok())


if __name__ == "__main__":
    unittest.main()
