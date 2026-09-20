"""巡检流水线现状行为的锁定测试。

scan / check / plan 的返回值与 stdout 输出都在锁定范围内；
stdout 断言是「接入日志层后输出不变」的基线。
"""

import io
import unittest
from contextlib import redirect_stdout

from loglite.checker import check
from loglite.manifest import dump, load, parse, parse_line, save
from loglite.planner import plan, summary
from loglite.scanner import scan

ENTRIES = [
    ("a.conf", 2048, 1000.0),
    ("b.tmp", 512, 1001.0),
    ("big.bin", 2097152, 1002.0),
    ("c.swp", 8, 1003.0),
]


def capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with redirect_stdout(buf):
        out = fn(*args, **kwargs)
    return out, buf.getvalue()


class TestManifest(unittest.TestCase):
    def test_parse_skips_comments_and_blank(self):
        text = "# head\n\na.txt 1 2\n"
        self.assertEqual(parse(text), [("a.txt", 1, 2)])

    def test_parse_name_keeps_spaces(self):
        self.assertEqual(parse_line("my file.txt 10 20"), ("my file.txt", 10, 20))

    def test_parse_bad_line_raises(self):
        with self.assertRaises(ValueError):
            parse_line("only-name")
        with self.assertRaises(ValueError):
            parse_line("x.txt abc 20")

    def test_dump_roundtrip(self):
        self.assertEqual(parse(dump(ENTRIES)), ENTRIES)

    def test_save_and_load_roundtrip(self):
        import os
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".manifest")
        os.close(fd)
        try:
            save(path, ENTRIES)
            self.assertEqual(load(path), ENTRIES)
        finally:
            os.unlink(path)


class TestScanner(unittest.TestCase):
    def test_flagged_names_in_order(self):
        out, _ = capture(scan, ENTRIES)
        self.assertEqual(out, ["b.tmp", "big.bin", "c.swp"])

    def test_clean_entries(self):
        out, _ = capture(scan, [("ok.txt", 1, 1)])
        self.assertEqual(out, [])

    def test_output_locked(self):
        _, out = capture(scan, ENTRIES)
        self.assertEqual(
            out.splitlines(),
            [
                "[scanner] start: 4 entries",
                "[scanner] flagged b.tmp (temp suffix)",
                "[scanner] flagged big.bin (size 2097152 over limit)",
                "[scanner] flagged c.swp (temp suffix)",
                "[scanner] done: 1 ok, 3 flagged",
            ],
        )


class TestChecker(unittest.TestCase):
    def test_duplicate_detected(self):
        entries = [("a", 1, 0.0), ("a", 1, 1.0), ("b", 1, 2.0)]
        out, _ = capture(check, entries, now=0.0)
        self.assertEqual(out, [("a", "DUPLICATE")])

    def test_future_mtime_detected(self):
        entries = [("a", 1, 10_000.0)]
        out, _ = capture(check, entries, now=0.0)
        self.assertEqual(out, [("a", "FUTURE_MTIME")])

    def test_margin_is_60s(self):
        # now+60 恰好不报，now+61 报
        out, _ = capture(check, [("a", 1, 60.0)], now=0.0)
        self.assertEqual(out, [])
        out, _ = capture(check, [("a", 1, 61.0)], now=0.0)
        self.assertEqual(out, [("a", "FUTURE_MTIME")])

    def test_output_locked(self):
        entries = [("a", 1, 0.0), ("a", 1, 90.0)]
        _, out = capture(check, entries, now=0.0)
        self.assertEqual(
            out.splitlines(),
            [
                "==> checker: begin over 2 entries",
                "==> checker: duplicate entry a",
                "==> checker: mtime in future: a",
                "==> checker: found 2 problem(s)",
            ],
        )


class TestPlanner(unittest.TestCase):
    def test_actions_keep_order(self):
        problems = [("a", "DUPLICATE"), ("b", "FUTURE_MTIME")]
        out, _ = capture(plan, problems)
        self.assertEqual(out, [("a", "drop-duplicate"), ("b", "touch-back")])

    def test_unknown_code_goes_manual(self):
        out, _ = capture(plan, [("x", "WEIRD")])
        self.assertEqual(out, [("x", "manual-review")])

    def test_summary_counts_by_action(self):
        actions = [("a", "drop-duplicate"), ("b", "touch-back"), ("c", "drop-duplicate")]
        self.assertEqual(summary(actions), {"drop-duplicate": 2, "touch-back": 1})

    def test_output_locked(self):
        _, out = capture(plan, [("a", "DUPLICATE")])
        self.assertEqual(
            out.splitlines(),
            [
                "[planner] building plan: 1 problem(s)",
                "[planner] #1 a -> drop-duplicate",
                "[planner] ready: 1 action(s)",
            ],
        )


class TestPipelineOutput(unittest.TestCase):
    def test_full_pipeline_stdout_locked(self):
        # 三段连跑，输出顺序也是行为的一部分
        buf = io.StringIO()
        with redirect_stdout(buf):
            scan(ENTRIES)
            check(ENTRIES, now=100000.0)
            plan([("big.bin", "FUTURE_MTIME")])
        self.assertEqual(
            buf.getvalue().splitlines(),
            [
                "[scanner] start: 4 entries",
                "[scanner] flagged b.tmp (temp suffix)",
                "[scanner] flagged big.bin (size 2097152 over limit)",
                "[scanner] flagged c.swp (temp suffix)",
                "[scanner] done: 1 ok, 3 flagged",
                "==> checker: begin over 4 entries",
                "==> checker: found 0 problem(s)",
                "[planner] building plan: 1 problem(s)",
                "[planner] #1 big.bin -> touch-back",
                "[planner] ready: 1 action(s)",
            ],
        )


if __name__ == "__main__":
    unittest.main()
