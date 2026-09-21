import json
import os
import tempfile
import unittest

from logpipe import JsonlFileSink, LogPipeline, MemorySink, clone, loads


def sample_record():
    return {
        "ts": "2026-09-21T09:00:00Z",
        "user": {"id": 7, "phone": "13812345678"},
        "payments": [{"card": "6222020200112233", "amount": 12.5}],
    }


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.sink = MemorySink()
        self.pipeline = LogPipeline(self.sink)

    def test_emit_returns_serialized_line(self):
        record = sample_record()
        line = self.pipeline.emit(record)
        self.assertEqual(len(self.sink.lines), 1)
        self.assertEqual(self.sink.lines[0], line)
        self.assertEqual(loads(line), record)

    def test_emit_does_not_mutate_record(self):
        record = sample_record()
        snapshot = clone(record)
        self.pipeline.emit(record)
        self.assertEqual(record, snapshot)

    def test_emitted_line_is_immune_to_later_changes(self):
        record = sample_record()
        line = self.pipeline.emit(record)
        record["user"]["phone"] = "changed"
        self.assertEqual(loads(line)["user"]["phone"], "13812345678")

    def test_non_dict_record_is_rejected(self):
        with self.assertRaises(TypeError):
            self.pipeline.emit(["not", "a", "record"])
        self.assertEqual(self.sink.lines, [])
        self.assertEqual(self.pipeline.emitted, 0)

    def test_emit_many_counts(self):
        written = self.pipeline.emit_many([sample_record(), {}])
        self.assertEqual(written, 2)
        self.assertEqual(self.pipeline.stats()["emitted"], 2)

    def test_empty_record_round_trip(self):
        line = self.pipeline.emit({})
        self.assertEqual(loads(line), {})


class ClosedSinkTests(unittest.TestCase):
    def test_write_after_close_is_rejected(self):
        sink = MemorySink()
        sink.close()
        with self.assertRaises(ValueError):
            sink.write("{}")

    def test_context_manager_closes(self):
        with MemorySink() as sink:
            sink.write("{}")
        self.assertTrue(sink.closed)
        self.assertEqual(sink.lines, ["{}"])


class JsonlFileSinkTests(unittest.TestCase):
    def test_appends_one_line_per_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "logs", "app.jsonl")
            record = sample_record()
            with JsonlFileSink(path) as sink:
                pipeline = LogPipeline(sink)
                pipeline.emit(record)
                pipeline.emit({})
                self.assertEqual(sink.count, 2)
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0]), record)
            self.assertEqual(json.loads(lines[1]), {})

    def test_close_then_write_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = JsonlFileSink(os.path.join(tmp, "app.jsonl"))
            sink.close()
            with self.assertRaises(ValueError):
                sink.write("{}")


if __name__ == "__main__":
    unittest.main()
