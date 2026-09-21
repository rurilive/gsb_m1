"""Future 状态机与取消语义的基线。"""

import unittest

from stealpool.errors import TaskCancelled
from stealpool.future import CANCELLED, FINISHED, PENDING, RUNNING, Future


class StateTest(unittest.TestCase):
    def test_result_round_trip(self):
        future = Future()
        self.assertEqual(future.state(), PENDING)
        self.assertFalse(future.done())
        self.assertFalse(future.cancelled())
        future.set_running_or_notify_cancel()
        self.assertTrue(future.running())
        future.set_result(41)
        self.assertEqual(future.state(), FINISHED)
        self.assertTrue(future.done())
        self.assertEqual(future.result(), 41)
        self.assertIsNone(future.exception())
        with self.assertRaises(TimeoutError):
            Future().result(0.01)

    def test_exception_round_trip(self):
        future = Future()
        future.set_running_or_notify_cancel()
        future.set_exception(ValueError("炸了"))
        with self.assertRaises(ValueError):
            future.result()
        self.assertIsInstance(future.exception(), ValueError)

    def test_illegal_transitions_rejected(self):
        future = Future()
        future.set_result(1)
        with self.assertRaises(RuntimeError):
            future.set_result(2)
        with self.assertRaises(RuntimeError):
            future.set_exception(ValueError())
        with self.assertRaises(RuntimeError):
            future.set_running_or_notify_cancel()


class CancelTest(unittest.TestCase):
    def test_cancel_pending_succeeds_and_skips_execution(self):
        future = Future()
        self.assertTrue(future.cancel())
        self.assertTrue(future.cancelled())
        self.assertTrue(future.done())
        self.assertEqual(future.state(), CANCELLED)
        self.assertFalse(future.set_running_or_notify_cancel())
        with self.assertRaises(TaskCancelled):
            future.result()

    def test_cancel_settled_returns_false(self):
        running = Future()
        running.set_running_or_notify_cancel()
        self.assertFalse(running.cancel())
        self.assertFalse(running.cancelled())
        finished = Future()
        finished.set_result(1)
        self.assertFalse(finished.cancel())
        self.assertEqual(finished.result(), 1)


class CallbackTest(unittest.TestCase):
    def test_callback_fires_on_completion_and_immediately_when_late(self):
        future = Future()
        seen = []
        future.add_done_callback(seen.append)
        self.assertEqual(seen, [])
        future.set_result(7)
        self.assertEqual(seen, [future])
        later = []
        future.add_done_callback(later.append)
        self.assertEqual(later, [future])

    def test_callback_fires_on_cancel(self):
        future = Future()
        seen = []
        future.add_done_callback(seen.append)
        future.cancel()
        self.assertEqual(seen, [future])


if __name__ == "__main__":
    unittest.main()
