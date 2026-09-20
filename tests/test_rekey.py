"""rekey 子流程：两稳态成功路径、各步超时回退、回退后可用。"""

import unittest

from handshake import Ev, ProtocolError, REKEY_TIMEOUT, Session, State


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def happy(clock, suite="strong"):
    """走完整握手进稳态。"""
    s = Session(clock=clock)
    s.feed(Ev.START)
    s.feed(Ev.PEER_HELLO, suite)
    s.feed(Ev.PEER_KEY)
    s.feed(Ev.PEER_AUTH_OK)
    return s


class TestRekeySuccess(unittest.TestCase):
    def test_rekey_from_full_returns_full(self):
        clock = FakeClock()
        s = happy(clock, "strong")
        s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "rekey-offer"))
        clock.advance(1.0)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        self.assertEqual(s.outbox[-1], (1.0, "rekey-confirm"))
        clock.advance(1.0)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(
            [m for _, m in s.outbox[-2:]],
            ["rekey-offer", "rekey-confirm"])
        self.assertEqual(s.log[-1].detail, "REKEY_CONFIRM_SENT->FULL")
        self.assertIsNone(s._deadline)

    def test_rekey_from_degraded_returns_degraded(self):
        clock = FakeClock()
        s = happy(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.DEGRADED)
        self.assertEqual(
            [m for _, m in s.outbox[-2:]],
            ["rekey-offer", "rekey-confirm"])
        self.assertEqual(s.suite, "weak")
        self.assertEqual(s.log[-1].detail, "REKEY_CONFIRM_SENT->DEGRADED")

    def test_rekey_timers_rearmed_each_step(self):
        clock = FakeClock()
        s = happy(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        # accept 到达后重新武装 5.0，旧 deadline 作废
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        clock.advance(REKEY_TIMEOUT - 0.2)
        s.poll()
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)


class TestRekeyTimeoutFallback(unittest.TestCase):
    def _check_rollback(self, suite, steady, event, late_state):
        clock = FakeClock()
        s = happy(clock, suite)
        s.feed(Ev.REKEY)
        if event is not None:
            s.feed(event)
        self.assertIs(s.state, late_state)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, steady)
        # 超时只回退：不发任何新消息
        self.assertEqual(s.outbox[-1][1], "rekey-confirm"
                         if late_state is State.REKEY_CONFIRM_SENT
                         else "rekey-offer")
        self.assertEqual([e.kind for e in s.log[-2:]], ["timeout", "move"])
        self.assertEqual(
            s.log[-2].detail, f"TIMEOUT in {late_state.value}")
        self.assertEqual(
            s.log[-1].detail, f"{late_state.value}->{steady.value}")
        # 回退后连接不断：稳态无定时器，poll 空操作
        clock.advance(100.0)
        s.poll()
        self.assertIs(s.state, steady)
        return s

    def test_offer_timeout_rolls_back_to_full(self):
        self._check_rollback(
            "strong", State.FULL, None, State.REKEY_OFFER_SENT)

    def test_offer_timeout_rolls_back_to_degraded(self):
        self._check_rollback(
            "weak", State.DEGRADED, None, State.REKEY_OFFER_SENT)

    def test_confirm_timeout_rolls_back_to_full(self):
        self._check_rollback(
            "strong", State.FULL, Ev.PEER_REKEY_ACCEPT,
            State.REKEY_CONFIRM_SENT)

    def test_confirm_timeout_rolls_back_to_degraded(self):
        self._check_rollback(
            "weak", State.DEGRADED, Ev.PEER_REKEY_ACCEPT,
            State.REKEY_CONFIRM_SENT)

    def test_timeout_boundary_just_before(self):
        clock = FakeClock()
        s = happy(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.001)
        s.poll()
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        clock.advance(0.001)
        s.poll()
        self.assertIs(s.state, State.FULL)


class TestUsableAfterFallback(unittest.TestCase):
    def test_rekey_again_succeeds_after_timeout(self):
        clock = FakeClock()
        s = happy(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(
            [m for _, m in s.outbox[-2:]],
            ["rekey-offer", "rekey-confirm"])

    def test_degraded_degraded_after_timeout_then_success(self):
        clock = FakeClock()
        s = happy(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.DEGRADED)

    def test_peer_close_still_works_after_fallback(self):
        clock = FakeClock()
        s = happy(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)
        self.assertEqual(s.outbox[-1], (REKEY_TIMEOUT, "c_close"))

    def test_rekey_rejected_in_nonsteady(self):
        s = Session(clock=FakeClock())
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)
        self.assertIs(s.state, State.CLOSED)

    def test_rekey_timeout_constant(self):
        self.assertEqual(REKEY_TIMEOUT, 5.0)


if __name__ == "__main__":
    unittest.main()
