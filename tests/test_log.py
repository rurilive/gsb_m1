"""结构化日志层测试：捕获、级别过滤、上下文嵌套/线程隔离、轮转不丢。"""

import glob
import io
import json
import os
import tempfile
import threading
import unittest
from collections import Counter
from contextlib import redirect_stdout

from loglite import logging as L
from loglite.checker import check
from loglite.planner import plan
from loglite.scanner import scan


class LogTestBase(unittest.TestCase):
    def setUp(self):
        L.reset()
        self.sink = L.CaptureSink()
        L.configure(sinks=[self.sink])

    def tearDown(self):
        L.reset()


class TestCaptureAndLevels(LogTestBase):
    def test_capture_holds_records_messages_and_lines(self):
        log = L.get_logger("demo")
        log.info("hello")
        self.assertEqual(self.sink.messages(), ["hello"])
        self.assertEqual(self.sink.lines, ["hello"])
        record = self.sink.records[0]
        self.assertEqual(record.level, L.INFO)
        self.assertEqual(record.name, "demo")
        self.assertEqual(record.message, "hello")
        self.assertEqual(record.thread_name, threading.current_thread().name)

    def test_below_global_level_dropped(self):
        log = L.get_logger()
        L.configure(level="WARNING")
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        self.assertEqual(self.sink.messages(), ["w", "e"])

    def test_debug_level_keeps_everything(self):
        log = L.get_logger()
        L.configure(level=L.DEBUG)
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        self.assertEqual(self.sink.messages(), ["d", "i", "w", "e"])

    def test_error_level_drops_lower(self):
        log = L.get_logger()
        L.configure(level="ERROR")
        log.warning("w")
        log.error("e")
        self.assertEqual(self.sink.messages(), ["e"])

    def test_level_change_takes_effect_afterwards(self):
        log = L.get_logger()
        log.debug("hidden")
        L.configure(level="DEBUG")
        log.debug("shown")
        self.assertEqual(self.sink.messages(), ["shown"])


class TestContext(LogTestBase):
    def test_context_attached_automatically(self):
        log = L.get_logger("scan")
        L.set_context(job="nightly", host="node-1")
        log.info("starting")
        self.assertEqual(self.sink.records[0].context, {"job": "nightly", "host": "node-1"})

    def test_nested_pop_returns_to_previous_layer(self):
        log = L.get_logger()
        outer = L.set_context(system="scanner", run="r1")
        log.info("outer")
        inner = L.set_context(system="checker", item="a.conf")
        log.info("inner")
        L.clear_context(inner)
        log.info("back-to-outer")
        self.assertEqual(
            self.sink.records[0].context,
            {"system": "scanner", "run": "r1"},
        )
        self.assertEqual(
            self.sink.records[1].context,
            {"system": "checker", "run": "r1", "item": "a.conf"},
        )
        self.assertEqual(
            self.sink.records[2].context,
            {"system": "scanner", "run": "r1"},
        )
        L.clear_context(outer)
        self.assertEqual(L.context(), {})

    def test_clear_context_pops_most_recent_layer(self):
        log = L.get_logger()
        L.set_context(a=1)
        L.set_context(b=2)
        L.clear_context()
        log.info("x")
        self.assertEqual(self.sink.records[0].context, {"a": 1})

    def test_context_manager_auto_pops_on_exit(self):
        log = L.get_logger()
        with L.set_context(stage="scan"):
            log.info("inside")
        log.info("outside")
        self.assertEqual(self.sink.records[0].context, {"stage": "scan"})
        self.assertEqual(self.sink.records[1].context, {})

    def test_context_isolated_between_threads(self):
        log = L.get_logger()
        errors = []

        def worker(value):
            try:
                L.set_context(item=value)
                barrier.wait(timeout=5)
                log.info(value)
            except Exception as exc:  # pragma: no cover - 失败路径
                errors.append(exc)

        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(target=worker, args=("thread-a",)),
            threading.Thread(target=worker, args=("thread-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        contexts = {record.message: record.context for record in self.sink.records}
        self.assertEqual(contexts["thread-a"], {"item": "thread-a"})
        self.assertEqual(contexts["thread-b"], {"item": "thread-b"})

    def test_main_thread_context_not_visible_in_worker(self):
        L.set_context(job="main-only")
        seen = []

        def worker():
            seen.append(L.context())

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(seen, [{}])
        self.assertEqual(L.context(), {"job": "main-only"})


class TestPlainCompat(LogTestBase):
    def test_plain_render_matches_old_print_byte_for_byte(self):
        entries = [
            ("a.conf", 2048, 1000.0),
            ("b.tmp", 512, 1001.0),
            ("big.bin", 2097152, 1002.0),
            ("c.swp", 8, 1003.0),
        ]
        buf = io.StringIO()
        L.reset()
        with redirect_stdout(buf):
            scan(entries)
            check(entries, now=100000.0)
            plan([("big.bin", "FUTURE_MTIME")])
        self.assertEqual(
            buf.getvalue(),
            "\n".join(
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
                    "",
                ]
            ),
        )


class FileRotationTestBase(unittest.TestCase):
    def setUp(self):
        L.reset()
        self.tmpdir = tempfile.mkdtemp(prefix="loglite-test-")
        self.path = os.path.join(self.tmpdir, "app.log")

    def tearDown(self):
        L.reset()
        for name in glob.glob(os.path.join(self.tmpdir, "app.log*")):
            os.remove(name)
        os.rmdir(self.tmpdir)

    def read_lines(self):
        lines = []
        names = [self.path]
        names.extend(glob.glob(f"{self.path}.*"))
        names.sort(key=lambda name: (name != self.path, name))
        for name in names:
            with open(name, "r", encoding="utf-8") as handle:
                lines.extend(handle.read().splitlines())
        return lines

    def json_messages(self):
        result = []
        for line in self.read_lines():
            result.append(json.loads(line))
        return result


class TestRotation(FileRotationTestBase):
    def test_rotation_shifts_backups_and_caps_count(self):
        sink = L.FileSink(self.path, max_bytes=200, backups=2)
        L.configure(sinks=[sink])
        log = L.get_logger("rot")
        for index in range(20):
            log.info(f"rotation-message-number-{index:03d}")
        sink.close()
        self.assertTrue(os.path.exists(self.path))
        self.assertTrue(os.path.exists(f"{self.path}.1"))
        self.assertTrue(os.path.exists(f"{self.path}.2"))
        self.assertFalse(os.path.exists(f"{self.path}.3"))

    def test_every_line_survives_single_threaded_rotation(self):
        sink = L.FileSink(self.path, max_bytes=200, backups=40)
        L.configure(sinks=[sink])
        log = L.get_logger("rot")
        messages = [f"msg-{i:03d}" for i in range(40)]
        for message in messages:
            log.info(message)
        sink.close()
        self.assertEqual(
            Counter(item["message"] for item in self.json_messages()),
            Counter(messages),
        )

    def test_json_payload_carries_level_logger_and_context(self):
        sink = L.FileSink(self.path, max_bytes=4096, backups=1)
        L.configure(sinks=[sink])
        log = L.get_logger("scanner")
        L.set_context(job="nightly")
        log.warning("disk almost full")
        sink.close()
        record = json.loads(self.read_lines()[0])
        self.assertEqual(record["level"], "WARNING")
        self.assertEqual(record["logger"], "scanner")
        self.assertEqual(record["message"], "disk almost full")
        self.assertEqual(record["context"], {"job": "nightly"})
        self.assertIn("thread", record)


class TestConcurrentRotation(FileRotationTestBase):
    def test_parallel_writers_lose_nothing_across_rotations(self):
        threads_count = 8
        per_thread = 60
        sink = L.FileSink(self.path, max_bytes=512, backups=120)
        L.configure(sinks=[sink])
        log = L.get_logger("busy")
        errors = []

        def worker(worker_id):
            try:
                for index in range(per_thread):
                    log.info(f"w{worker_id:02d}-m{index:03d}")
            except Exception as exc:  # pragma: no cover - 失败路径
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(worker_id,))
            for worker_id in range(threads_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        sink.close()
        self.assertEqual(errors, [])

        records = self.json_messages()
        expected = [
            f"w{worker_id:02d}-m{index:03d}"
            for worker_id in range(threads_count)
            for index in range(per_thread)
        ]
        self.assertEqual(len(records), len(expected))
        self.assertEqual(
            Counter(record["message"] for record in records), Counter(expected)
        )

    def test_writers_blocked_during_rotation_do_not_lose_lines(self):
        # 用 Event 定节奏：轮转开始后放行一批写线程，让它们挤在
        # “当前文件已轮走、新文件尚未打开”的窗口上。
        rotation_started = threading.Event()
        release_rotation = threading.Event()
        writers_armed = threading.Event()
        sink = L.FileSink(self.path, max_bytes=4096, backups=10,
                          on_rotate=lambda: (rotation_started.set(),
                                             release_rotation.wait(timeout=5)))
        L.configure(sinks=[sink])
        log = L.get_logger("race")
        errors = []
        writers_count = 6
        per_writer = 25

        def filler():
            try:
                log.info("x" * 4090)  # 撑爆当前文件，触发轮转
            except Exception as exc:  # pragma: no cover - 失败路径
                errors.append(exc)

        def writer(writer_id):
            try:
                writers_armed.set()
                release_rotation.wait(timeout=5)
                for index in range(per_writer):
                    log.info(f"t{writer_id}-{index}")
            except Exception as exc:  # pragma: no cover - 失败路径
                errors.append(exc)

        filler_thread = threading.Thread(target=filler)
        writer_threads = [
            threading.Thread(target=writer, args=(writer_id,))
            for writer_id in range(writers_count)
        ]
        filler_thread.start()
        self.assertTrue(rotation_started.wait(timeout=5))
        for thread in writer_threads:
            thread.start()
        self.assertTrue(writers_armed.wait(timeout=5))
        release_rotation.set()
        filler_thread.join()
        for thread in writer_threads:
            thread.join()
        sink.close()
        self.assertEqual(errors, [])

        records = self.json_messages()
        expected = [
            f"t{writer_id}-{index}"
            for writer_id in range(writers_count)
            for index in range(per_writer)
        ]
        # 触发轮转的那条 + 挤在轮转窗口上的所有记录都必须在
        self.assertEqual(len(records), 1 + len(expected))
        counts = Counter(record["message"] for record in records)
        self.assertEqual(counts["x" * 4090], 1)
        for message in expected:
            self.assertEqual(counts[message], 1)

    def test_same_file_never_rotated_twice_concurrently(self):
        mid_rotation_observations = []
        guard = threading.Lock()

        def on_rotate():
            # 回调在“旧文件已改名、新文件尚未打开”之间执行；
            # 若同一文件被轮两次，可能在此观察到残留的同名当前文件。
            with guard:
                mid_rotation_observations.append(os.path.exists(self.path))

        sink = L.FileSink(self.path, max_bytes=300, backups=40, on_rotate=on_rotate)
        L.configure(sinks=[sink])
        log = L.get_logger("rot2")
        threads_count = 6

        def worker():
            for index in range(20):
                log.info(f"concurrent-rotation-line-{index}")

        threads = [threading.Thread(target=worker) for _ in range(threads_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        sink.close()
        # 每次轮转都串行完成：回调时当前路径必然还不存在，
        # 备份文件个数严格不超过 backups，且记录一条不重、一条不丢。
        self.assertTrue(mid_rotation_observations)
        self.assertFalse(any(mid_rotation_observations))
        self.assertLessEqual(
            len(glob.glob(os.path.join(self.tmpdir, "app.log.*"))), 40
        )
        messages = Counter(record["message"] for record in self.json_messages())
        self.assertEqual(
            messages,
            Counter({f"concurrent-rotation-line-{index}": threads_count
                     for index in range(20)}),
        )


if __name__ == "__main__":
    unittest.main()
