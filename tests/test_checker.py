"""同步检查器的锁定测试。"""

import unittest

from healthd import CheckRunner, StatusBoard


class TestCheckRunner(unittest.TestCase):
    def test_register_order_and_dup(self):
        r = CheckRunner()
        r.register("a", lambda: "")
        r.register("b", lambda: "")
        self.assertEqual(r.names(), ["a", "b"])
        with self.assertRaises(ValueError):
            r.register("a", lambda: "")

    def test_run_once_all_pass(self):
        r = CheckRunner()
        r.register("db", lambda: "primary")
        snap = r.run_once()
        self.assertTrue(snap["db"].ok)
        self.assertEqual(snap["db"].detail, "primary")
        self.assertTrue(r.board.overall_ok())

    def test_failure_does_not_stop_later_probes(self):
        def boom():
            raise RuntimeError("conn refused")

        r = CheckRunner()
        r.register("db", boom)
        r.register("q", lambda: "depth=3")
        snap = r.run_once()
        self.assertFalse(snap["db"].ok)
        self.assertIn("conn refused", snap["db"].detail)
        self.assertTrue(snap["q"].ok)
        self.assertFalse(r.board.overall_ok())

    def test_runs_in_registration_order(self):
        seen = []

        r = CheckRunner()
        r.register("a", lambda: seen.append("a") or "")
        r.register("b", lambda: seen.append("b") or "")
        r.run_once()
        self.assertEqual(seen, ["a", "b"])

    def test_detail_defaults_empty(self):
        r = CheckRunner()
        r.register("always", lambda: None)
        snap = r.run_once()
        self.assertTrue(snap["always"].ok)
        self.assertEqual(snap["always"].detail, "")

    def test_uses_custom_board(self):
        board = StatusBoard()
        r = CheckRunner(board=board)
        r.register("x", lambda: "")
        r.run_once()
        self.assertTrue(board.result("x").ok)


if __name__ == "__main__":
    unittest.main()
