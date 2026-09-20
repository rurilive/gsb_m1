"""结构化日志层的新行为测试。

覆盖：记录捕获与级别过滤、上下文嵌套与线程隔离、文件按大小轮转
（单线程顺序 + 多线程 Event 定节奏，轮转不丢日志、同一文件不轮两次）、
兼容模式渲染与旧 print 逐行一致。
"""

import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from loglite.logging import (
    INFO,
    WARNING,
    CaptureSink,
    RotatingFileSink,
    configure,
    get_context,
    get_logger,
    reset_context,
    reset_defaults,
    render_compat,
    render_json,
    render_plain,
    set_context,
    set_level,
)
from loglite.scanner import scan

ENTRIES = [
    ("a.conf", 2048, 1000.0),
    ("b.tmp", 512, 1001.0),
    ("big.bin", 2097152, 1002.0),
    ("c.swp", 8, 1003.0),
]

LINE11 = "0123456789a"  # 11 字符，加 \n 后落盘 12 字节


class LogTestBase(unittest.TestCase):
    def setUp(self):
        reset_defaults()

    def tearDown(self):
        reset_defaults()


class TestCaptureAndLevels(LogTestBase):
    def test_capture_full_record_and_fields(self):
        sink = CaptureSink(renderer=render_plain)
        configure(level="DEBUG", sink=sink)
        log = get_logger("demo")
        with set_context(subsystem="scan"):
            log.info("hello", request="r1")
        record = sink.records[0]
        self.assertEqual(record["msg"], "hello")
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["levelno"], INFO)
        self.assertEqual(record["name"], "demo")
        self.assertEqual(record["subsystem"], "scan")
        self.assertEqual(record["request"], "r1")
        self.assertIn("time", record)
        line = sink.lines[0]
        self.assertIn("INFO", line)
        self.assertIn("demo", line)
        self.assertIn("hello", line)
        self.assertIn("subsystem=scan", line)
        self.assertIn("request=r1", line)

    def test_records_below_global_level_are_dropped(self):
        sink = CaptureSink()
        configure(level=WARNING, sink=sink)
        log = get_logger("demo")
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        self.assertEqual([r["msg"] for r in sink.records], ["w", "e"])

    def test_level_boundaries(self):
        sink = CaptureSink()
        configure(sink=sink)
        log = get_logger("demo")
        set_level("DEBUG")
        log.debug("d")
        self.assertEqual(sink.records[-1]["level"], "DEBUG")
        set_level("INFO")
        log.debug("d2")
        log.info("i")
        self.assertEqual([r["msg"] for r in sink.records], ["d", "i"])
        set_level("ERROR")
        log.warning("w")
        log.error("e")
        self.assertEqual(sink.records[-1]["msg"], "e")
        self.assertEqual(len(sink.records), 3)

    def test_invalid_level_raises(self):
        with self.assertRaises(ValueError):
            set_level("TRACE")
        with self.assertRaises(ValueError):
            set_level(99)

    def test_reserved_extra_key_raises(self):
        log = get_logger("demo")
        with self.assertRaises(ValueError):
            log.info("x", time=1)
        with self.assertRaises(ValueError):
            log.info("x", level="DEBUG")

    def test_renderers(self):
        record = {
            "time": 1.5,
            "level": "INFO",
            "levelno": INFO,
            "name": "demo",
            "msg": "hello",
            "k": "v",
        }
        self.assertEqual(render_compat(record), "hello")
        self.assertEqual(
            render_plain(record), "1.500 | INFO | demo | hello | k=v"
        )
        decoded = json.loads(render_json(record))
        self.assertEqual(decoded["msg"], "hello")
        self.assertEqual(decoded["k"], "v")


class TestContext(LogTestBase):
    def test_context_auto_attached_and_cleared(self):
        sink = CaptureSink()
        configure(sink=sink)
        log = get_logger("demo")
        token = set_context(subsystem="scan", job="j1")
        log.info("inside")
        token.clear()
        log.info("outside")
        self.assertEqual(sink.records[0]["subsystem"], "scan")
        self.assertEqual(sink.records[0]["job"], "j1")
        self.assertNotIn("subsystem", sink.records[1])
        self.assertNotIn("job", sink.records[1])

    def test_nested_pop_one_restores_previous_layer(self):
        sink = CaptureSink()
        configure(sink=sink)
        log = get_logger("demo")
        outer = set_context(subsystem="scan", layer="outer")
        log.info("outer-line")
        inner = set_context(layer="inner", stage="check")
        log.info("inner-line")
        self.assertEqual(get_context()["subsystem"], "scan")
        self.assertEqual(get_context()["layer"], "inner")
        self.assertEqual(get_context()["stage"], "check")
        inner.clear()
        log.info("back-to-outer")
        ctx = {
            key: value
            for key, value in sink.records[-1].items()
            if key not in ("time", "level", "levelno", "name", "msg")
        }
        self.assertEqual(ctx, {"subsystem": "scan", "layer": "outer"})
        outer.clear()
        self.assertEqual(get_context(), {})

    def test_context_manager_protocol(self):
        sink = CaptureSink()
        configure(sink=sink)
        log = get_logger("demo")
        with set_context(a="1"):
            self.assertEqual(get_context()["a"], "1")
            with set_context(b="2"):
                log.info("deep")
                self.assertEqual(sink.records[-1]["b"], "2")
            self.assertNotIn("b", get_context())
            self.assertEqual(get_context()["a"], "1")
        self.assertEqual(get_context(), {})

    def test_clear_non_top_frame_keeps_stack_intact(self):
        outer = set_context(a="1")
        set_context(b="2")
        outer.clear()  # 非栈顶令牌：不弹任何帧
        self.assertEqual(get_context(), {"a": "1", "b": "2"})
        outer.clear()  # 幂等
        self.assertEqual(get_context(), {"a": "1", "b": "2"})
        reset_context()

    def test_threads_do_not_share_context(self):
        sink = CaptureSink()
        ready = threading.Event()
        done = threading.Event()

        def worker():
            configure(sink=sink)
            reset_context()
            with set_context(subsystem="worker"):
                ready.wait(timeout=5)
                get_logger("worker").info("from-thread")
            done.set()

        with set_context(subsystem="main"):
            thread = threading.Thread(target=worker)
            thread.start()
            ready.set()
            self.assertTrue(done.wait(timeout=5))
            thread.join()
            get_logger("demo").info("from-main")
        thread_record = next(r for r in sink.records if r["name"] == "worker")
        main_record = next(r for r in sink.records if r["name"] == "demo")
        self.assertEqual(thread_record["subsystem"], "worker")
        self.assertEqual(main_record["subsystem"], "main")

    def test_new_thread_starts_with_empty_context(self):
        seen = []

        def worker():
            seen.append(get_context())

        with set_context(subsystem="main"):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
        self.assertEqual(seen, [{}])


def _line_sink(path, max_bytes, backups=2):
    return RotatingFileSink(
        path, max_bytes, backups, renderer=lambda record: record["msg"]
    )


def _read(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _msg(tag, idx):
    return f"{tag}{idx:<{11 - len(tag)}}"


class TestRotation(LogTestBase):
    def test_rollover_shift_and_no_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.txt")
            sink = _line_sink(path, max_bytes=30, backups=2)
            # 每行 12 字节：第 3、5 行写入前 30 字节装不下，触发轮转
            for idx in range(1, 6):
                sink.emit({"msg": _msg("L", idx)})
            sink.close()
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.exists(path + ".1"))
            self.assertTrue(os.path.exists(path + ".2"))
            self.assertFalse(os.path.exists(path + ".3"))
            ordered = _read(path + ".2") + _read(path + ".1") + _read(path)
            lines = ordered.splitlines()
            self.assertEqual(
                [line.strip() for line in lines],
                ["L1", "L2", "L3", "L4", "L5"],
            )
            self.assertEqual(len(lines), 5)
            self.assertEqual(_read(path), _msg("L", 5) + "\n")

    def test_backups_zero_keeps_no_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.txt")
            sink = _line_sink(path, max_bytes=30, backups=0)
            for idx in range(1, 6):
                sink.emit({"msg": _msg("M", idx)})
            sink.close()
            self.assertTrue(os.path.exists(path))
            self.assertFalse(os.path.exists(path + ".1"))

    def test_oldest_backup_is_evicted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.txt")
            sink = _line_sink(path, max_bytes=30, backups=1)
            for idx in range(1, 8):
                sink.emit({"msg": _msg("E", idx)})
            sink.close()
            self.assertEqual(
                sorted(os.listdir(tmp)), ["log.txt", "log.txt.1"]
            )

    def test_concurrent_writers_no_loss_or_duplicate(self):
        thread_count = 8
        per_thread = 40
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.txt")
            # 每条 13 字节；backups 足够大，旧文件永不淘汰，便于逐行对账
            sink = _line_sink(path, max_bytes=13 * 6 + 1, backups=100)
            errors = []

            def worker(tid):
                try:
                    for seq in range(per_thread):
                        sink.emit({"msg": f"t{tid:02d}-{seq:08d}"})
                except Exception as exc:  # pragma: no cover - 丢日志即对账失败
                    errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=(tid,))
                for tid in range(thread_count)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            sink.close()
            self.assertEqual(errors, [])
            written = []
            for name in os.listdir(tmp):
                with open(os.path.join(tmp, name), "r", encoding="utf-8") as f:
                    written.extend(
                        line.strip() for line in f if line.strip()
                    )
            expected = {
                f"t{tid:02d}-{seq:08d}"
                for tid in range(thread_count)
                for seq in range(per_thread)
            }
            self.assertEqual(len(written), thread_count * per_thread)
            self.assertEqual(set(written), expected)
            self.assertEqual(len(written), len(set(written)))

    def test_concurrent_rollover_runs_once_with_event_pacing(self):
        class PacedSink(RotatingFileSink):
            def __init__(self, path):
                super().__init__(
                    path, 30, 2, renderer=lambda record: record["msg"]
                )
                self.entered = threading.Event()
                self.proceed = threading.Event()
                self.rollover_count = 0

            def _on_rollover(self):
                self.rollover_count += 1
                if self.rollover_count == 1:
                    self.entered.set()
                    self.proceed.wait(timeout=5)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.txt")
            sink = PacedSink(path)
            sink.emit({"msg": LINE11})  # 12 字节
            sink.emit({"msg": LINE11})  # 累计 24 字节
            self.assertEqual(sink.rollover_count, 0)

            def writer(tag):
                sink.emit({"msg": tag})  # 10 字符 + \n = 11 字节

            t1 = threading.Thread(target=writer, args=("newline-t1",))
            t2 = threading.Thread(target=writer, args=("newline-t2",))
            t1.start()
            t2.start()
            self.assertTrue(sink.entered.wait(timeout=5))
            # 轮转进行中：恰好一个线程进入；path.1 尚未生成，日志无丢失
            self.assertEqual(sink.rollover_count, 1)
            self.assertFalse(os.path.exists(path + ".1"))
            self.assertTrue(os.path.exists(path))
            sink.proceed.set()
            t1.join()
            t2.join()
            sink.close()
            # 第二个线程拿锁后新文件还装得下，不会再次轮转同一文件
            self.assertEqual(sink.rollover_count, 1)
            self.assertTrue(os.path.exists(path + ".1"))
            self.assertFalse(os.path.exists(path + ".2"))
            backup = _read(path + ".1")
            current = _read(path)
            self.assertEqual(backup, LINE11 + "\n" + LINE11 + "\n")
            self.assertEqual(
                sorted(current.splitlines()), ["newline-t1", "newline-t2"]
            )
            self.assertEqual(current.count("newline-t1"), 1)
            self.assertEqual(current.count("newline-t2"), 1)


class TestCompatRendering(LogTestBase):
    def test_default_logger_matches_old_print_line_by_line(self):
        reset_defaults()
        buf = io.StringIO()
        with redirect_stdout(buf):
            scan(ENTRIES)
        self.assertEqual(
            buf.getvalue().splitlines(),
            [
                "[scanner] start: 4 entries",
                "[scanner] flagged b.tmp (temp suffix)",
                "[scanner] flagged big.bin (size 2097152 over limit)",
                "[scanner] flagged c.swp (temp suffix)",
                "[scanner] done: 1 ok, 3 flagged",
            ],
        )

    def test_default_stdout_is_byte_identical_to_print(self):
        reset_defaults()
        expected = io.StringIO()
        actual = io.StringIO()
        with redirect_stdout(expected):
            print("[scanner] start: 4 entries")
        with redirect_stdout(actual):
            get_logger("scanner").info("[scanner] start: 4 entries")
        self.assertEqual(actual.getvalue(), expected.getvalue())
        self.assertEqual(actual.getvalue(), "[scanner] start: 4 entries\n")

    def test_explicit_compat_stream_sink_strips_decoration(self):
        from loglite.logging import StreamSink

        stream = io.StringIO()
        configure(
            level="DEBUG",
            sink=StreamSink(stream=stream, renderer=render_compat),
        )
        with set_context(subsystem="scan"):
            get_logger("scanner").info("[scanner] flagged b.tmp (temp suffix)")
            get_logger("scanner").debug("[scanner] debug detail")
        self.assertEqual(
            stream.getvalue(),
            "[scanner] flagged b.tmp (temp suffix)\n"
            "[scanner] debug detail\n",
        )
