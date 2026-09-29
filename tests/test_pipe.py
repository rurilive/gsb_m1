"""run_stream 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from pipeflow import run_stream


class TestRunStreamOrder(unittest.TestCase):
    def test_processes_every_record_in_order(self):
        seen = []

        def process(record):
            seen.append(record)
            return record

        def sink(acc, value):
            acc.append(value)
            return acc

        result = run_stream([1, 2, 3], process, sink, initial=[])
        self.assertEqual(seen, [1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_process_transforms_value(self):
        result = run_stream([1, 2, 3], lambda r: r * 10, lambda acc, v: acc + v, initial=0)
        self.assertEqual(result, 60)

    def test_empty_source_yields_initial(self):
        result = run_stream([], lambda r: r, lambda acc, v: acc + v, initial=42)
        self.assertEqual(result, 42)

    def test_sink_can_change_value_type(self):
        result = run_stream(
            ["a", "b"],
            lambda r: r.upper(),
            lambda acc, v: acc + [v],
            initial=[],
        )
        self.assertEqual(result, ["A", "B"])


class TestRunStreamErrors(unittest.TestCase):
    def test_error_propagates_and_aborts(self):
        visited = []

        def process(record):
            if record == 2:
                raise ValueError("boom")
            return record

        def sink(acc, value):
            visited.append(value)
            return acc

        with self.assertRaises(ValueError):
            run_stream([1, 2, 3], process, sink, initial=None)
        self.assertEqual(visited, [1])

    def test_returns_none_when_initial_none(self):
        result = run_stream(["x"], lambda r: r, lambda acc, v: v)
        self.assertEqual(result, "x")


if __name__ == "__main__":
    unittest.main()
