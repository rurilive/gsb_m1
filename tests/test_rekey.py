"""rekey 子流程行为测试：时钟注入定节奏。

覆盖：FULL/DEGRADED 两稳态成功路径、offer/confirm 两步等待各自的
超时回退、回退后会话仍然可用。
"""

import unittest

from handshake import Ev, ProtocolError, REKEY_TIMEOUT, Session, State


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def reach_steady(clock, suite):
    """走完整握手进稳态。"""
    s = Session(clock=clock)
    s.feed(Ev.START)
    s.feed(Ev.PEER_HELLO, suite)
    s.feed(Ev.PEER_KEY)
    s.feed(Ev.PEER_AUTH_OK)
    return s


def rekey_success(session):
    """触发 rekey 并完成三步协商。"""
    session.feed(Ev.REKEY)
    session.feed(Ev.PEER_REKEY_ACCEPT)
    session.feed(Ev.PEER_REKEY_DONE)


class TestRekeySuccess(unittest.TestCase):
    def test_rekey_timeout_constant(self):
        self.assertEqual(REKEY_TIMEOUT, 5.0)

    def test_rekey_from_full_roundtrip(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "rekey-offer"))
        s.feed(Ev.PEER_REKEY_ACCEPT)
        self.assertIs(s.state, State.REKEY_CONFIRM_SENT)
        self.assertEqual(s.outbox[-1], (0.0, "rekey-confirm"))
        s.feed(Ev.PEER_REKEY_DONE)
        self.assertIs(s.state, State.FULL)
        self.assertEqual(
            [m for _, m in s.outbox[-3:]],
            ["rekey-offer", "rekey-confirm", "rekey-done-ack"])

    def test_rekey_from_degraded_returns_degraded(self):
        clock = FakeClock()
        s = reach_steady(clock, "weak")
        rekey_success(s)
        self.assertIs(s.state, State.DEGRADED)

    def test_rekey_success_no_timer_in_steady(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        rekey_success(s)
        clock.advance(100.0)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_rekey_moves_dynamic_target(self):
        clock = FakeClock()
        s = reach_steady(clock, "weak")
        rekey_success(s)
        self.assertEqual(
            [e.detail for e in s.log if e.kind == "move"][-3:],
            [
                "DEGRADED->REKEY_OFFER_SENT",
                "REKEY_OFFER_SENT->REKEY_CONFIRM_SENT",
                "REKEY_CONFIRM_SENT->DEGRADED",
            ])

    def test_rekey_all_events_logged(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        rekey_success(s)
        details = [e.detail for e in s.log if e.kind == "recv"]
        self.assertEqual(
            details[-3:],
            ["REKEY", "PEER_REKEY_ACCEPT", "PEER_REKEY_DONE"])


class TestRekeyTimeouts(unittest.TestCase):
    def test_offer_timeout_returns_full(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT - 0.1)
        s.poll()
        self.assertIs(s.state, State.REKEY_OFFER_SENT)
        clock.advance(0.1)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_offer_timeout_returns_degraded(self):
        clock = FakeClock()
        s = reach_steady(clock, "weak")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)

    def test_confirm_timeout_returns_degraded(self):
        clock = FakeClock()
        s = reach_steady(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)

    def test_confirm_timeout_returns_full(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)

    def test_timeout_logged_before_move(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual([e.kind for e in s.log[-2:]], ["timeout", "move"])
        self.assertEqual(
            s.log[-2].detail,
            f"TIMEOUT in {State.REKEY_OFFER_SENT.value}")

    def test_timeout_discards_new_key_no_send(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        sent = [m for _, m in s.outbox]
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertEqual([m for _, m in s.outbox], sent)


class TestRekeyRollbackUsable(unittest.TestCase):
    def test_rekey_again_after_offer_timeout(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.FULL)
        rekey_success(s)
        self.assertIs(s.state, State.FULL)

    def test_rekey_again_after_confirm_timeout(self):
        clock = FakeClock()
        s = reach_steady(clock, "weak")
        s.feed(Ev.REKEY)
        s.feed(Ev.PEER_REKEY_ACCEPT)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        self.assertIs(s.state, State.DEGRADED)
        rekey_success(s)
        self.assertIs(s.state, State.DEGRADED)

    def test_close_after_rollback(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        s.feed(Ev.REKEY)
        clock.advance(REKEY_TIMEOUT)
        s.poll()
        s.feed(Ev.PEER_CLOSE)
        self.assertIs(s.state, State.CLOSED)
        self.assertEqual(s.outbox[-1], (REKEY_TIMEOUT, "c_close"))

    def test_rekey_rejected_outside_steady(self):
        clock = FakeClock()
        s = Session(clock=clock)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.REKEY)

    def test_unexpected_peer_events_rejected(self):
        clock = FakeClock()
        s = reach_steady(clock, "strong")
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_DONE)
        s.feed(Ev.REKEY)
        with self.assertRaises(ProtocolError):
            s.feed(Ev.PEER_REKEY_DONE)


if __name__ == "__main__":
    unittest.main()
