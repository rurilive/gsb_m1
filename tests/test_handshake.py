"""handshake 现有行为的锁定测试。"""

import unittest

from handshake import (
    Ev,
    ProtocolError,
    Session,
    State,
    T_AUTH,
    T_HELLO,
    T_KEY,
)


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def happy(clock, suite="strong"):
    """走完整握手，返回会话。"""
    s = Session(clock=clock)
    s.feed(Ev.START)
    s.feed(Ev.PEER_HELLO, suite)
    s.feed(Ev.PEER_KEY)
    s.feed(Ev.PEER_AUTH_OK)
    return s


class TestHandshake(unittest.TestCase):
    def test_initial_state_closed(self):
        s = Session(clock=FakeClock())
        self.assertIs(s.state, State.CLOSED)
        self.assertIsNone(s.suite)
        self.assertEqual(s.outbox, [])

    def test_start_sends_hello(self):
        s = Session(clock=FakeClock())
        s.feed(Ev.START)
        self.assertIs(s.state, State.HELLO_SENT)
        self.assertEqual(s.outbox, [(0.0, "c_hello")])

    def test_happy_path_full(self):
        s = happy(FakeClock(), "strong")
        self.assertIs(s.state, State.FULL)
        self.assertEqual(s.suite, "strong")
        self.assertEqual(
            [m for _, m in s.outbox], ["c_hello", "c_key", "c_auth"])

    def test_weak_suite_degraded(self):
        s = happy(FakeClock(), "weak")
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(s.suite, "weak")

    def test_suite_stored_at_hello(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        s.feed(Ev.PEER_HELLO, "weak")
        self.assertIs(s.state, State.KEY_SENT)
        self.assertEqual(s.suite, "weak")

    def test_unknown_suite_rejected(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_HELLO, "quantum")
        self.assertIs(s.state, State.HELLO_SENT)

    def test_auth_fail_closes(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        s.feed(Ev.PEER_HELLO, "strong")
        s.feed(Ev.PEER_KEY)
        s.feed(Ev.PEER_AUTH_FAIL)
        self.assertIs(s.state, State.CLOSED)
        self.assertEqual(s.outbox[-1], (0.0, "c_close"))

    def test_invalid_event_raises(self):
        s = Session(clock=FakeClock())
        with self.assertRaises(ProtocolError) as cm:
            s.feed(Ev.PEER_KEY)
        self.assertIn("CLOSED", str(cm.exception))
        self.assertIn("PEER_KEY", str(cm.exception))

    def test_invalid_event_in_steady(self):
        s = happy(FakeClock())
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_HELLO, "strong")


class TestTimeouts(unittest.TestCase):
    def test_hello_timeout_boundary(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        clock.advance(T_HELLO - 0.1)
        s.poll()
        self.assertIs(s.state, State.HELLO_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.CLOSED)

    def test_key_timeout(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        s.feed(Ev.PEER_HELLO, "strong")
        clock.advance(T_KEY + 0.5)
        s.poll()
        self.assertIs(s.state, State.CLOSED)

    def test_auth_timeout(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        s.feed(Ev.PEER_HELLO, "weak")
        s.feed(Ev.PEER_KEY)
        clock.advance(T_AUTH)
        s.poll()
        self.assertIs(s.state, State.CLOSED)

    def test_poll_noop_without_timer(self):
        clock = FakeClock()
        s = happy(FakeClock())
        clock.advance(100.0)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_timeout_logged_before_move(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        clock.advance(T_HELLO)
        s.poll()
        self.assertEqual(
            [e.kind for e in s.log[-2:]], ["timeout", "move"])
        self.assertEqual(
            s.log[-2].detail, f"TIMEOUT in {State.HELLO_SENT.value}")

    def test_rehandshake_after_close(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        clock.advance(T_HELLO)
        s.poll()
        s.feed(Ev.START)
        s.feed(Ev.PEER_HELLO, "strong")
        s.feed(Ev.PEER_KEY)
        s.feed(Ev.PEER_AUTH_OK)
        self.assertIs(s.state, State.FULL)


class TestLogAndClock(unittest.TestCase):
    def test_log_kinds_sequence(self):
        clock = FakeClock()
        s = happy(clock)
        self.assertEqual(
            [e.kind for e in s.log],
            ["recv", "move", "send"] * 3 + ["recv", "move"],
        )

    def test_log_ts_follows_clock(self):
        clock = FakeClock()
        s = Session(clock=clock)
        s.feed(Ev.START)
        clock.advance(1.0)
        s.feed(Ev.PEER_HELLO, "strong")
        clock.advance(2.0)
        s.feed(Ev.PEER_KEY)
        self.assertEqual([e.ts for e in s.log], [0, 0, 0, 1, 1, 1, 3, 3, 3])
        self.assertEqual(s.log[7].detail, "KEY_SENT->AUTH_SENT")

    def test_move_details(self):
        clock = FakeClock()
        s = happy(clock)
        self.assertEqual(
            [e.detail for e in s.log if e.kind == "move"],
            [
                "CLOSED->HELLO_SENT",
                "HELLO_SENT->KEY_SENT",
                "KEY_SENT->AUTH_SENT",
                "AUTH_SENT->FULL",
            ],
        )

    def test_peer_close_from_steady(self):
        clock = FakeClock()
        s = happy(clock)
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)
        self.assertEqual(s.outbox[-1], (0.0, "c_close"))

    def test_timers_are_module_constants(self):
        self.assertEqual(T_HELLO, 3.0)
        self.assertEqual(T_KEY, 3.0)
        self.assertEqual(T_AUTH, 3.0)


if __name__ == "__main__":
    unittest.main()
