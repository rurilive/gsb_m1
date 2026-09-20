"""detached 现有行为的锁定测试（确定性，不依赖时序）。"""

import threading
import unittest

from tracectx.detached import async_call, run_detached


class TestRunDetached(unittest.TestCase):
    def test_returns_value(self):
        self.assertEqual(run_detached(pow, 2, 10), 1024)

    def test_reraises_original_exception(self):
        marker = ValueError("boom")

        def boom():
            raise marker

        with self.assertRaises(ValueError) as cm:
            run_detached(boom)
        self.assertIs(cm.exception, marker)

    def test_timeout_raises_and_frees_caller(self):
        ev = threading.Event()
        try:
            with self.assertRaises(TimeoutError):
                run_detached(ev.wait, 10, timeout=0.2)
        finally:
            ev.set()

    def test_without_timeout_waits_for_slow_task(self):
        ev = threading.Event()
        threading.Timer(0.2, ev.set).start()

        def slow():
            ev.wait(5)
            return "done"

        self.assertEqual(run_detached(slow), "done")


class TestAsyncCall(unittest.TestCase):
    def test_on_done_called_with_result(self):
        done = threading.Event()
        box = []

        def on_done(v):
            box.append(v)
            done.set()

        t = async_call(lambda: 42, on_done=on_done)
        self.assertTrue(done.wait(5))
        t.join(5)
        self.assertEqual(box, [42])

    def test_on_error_called_with_exception(self):
        err = threading.Event()
        box = []
        marker = KeyError("k")

        def fn():
            raise marker

        def on_error(exc):
            box.append(exc)
            err.set()

        t = async_call(fn, on_error=on_error)
        self.assertTrue(err.wait(5))
        t.join(5)
        self.assertIs(box[0], marker)

    def test_silent_without_callbacks(self):
        def fn():
            raise RuntimeError("ignored")

        t = async_call(fn)
        t.join(5)
        self.assertFalse(t.is_alive())

    def test_returns_thread(self):
        ev = threading.Event()
        t = async_call(ev.set)
        self.assertIsInstance(t, threading.Thread)
        self.assertTrue(ev.wait(5))
        t.join(5)


if __name__ == "__main__":
    unittest.main()
