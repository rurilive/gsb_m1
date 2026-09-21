"""崩溃恢复对拍：含幂等发放、并发重试、崩溃重启的脚本逐条一致。"""

import unittest

from leasekeeper.clock import FakeClock
from leasekeeper.durable import DurableLeaseKeeper
from leasekeeper.journal import MemoryJournal
from leasekeeper.script import (
    drive_durable,
    make_durable_script,
    model_durable,
)


def _check(seed, resources, steps=300):
    script = make_durable_script(seed=seed, resources=resources, steps=steps)
    clock = FakeClock()
    journal = MemoryJournal()

    def make_boot(existing):
        if existing is None:
            return DurableLeaseKeeper(clock=clock.current, journal=journal)
        return DurableLeaseKeeper.recover(existing, clock=clock.current)

    got = drive_durable(make_boot, script, clock)
    want, final = model_durable(script)
    return got, want, final, journal, clock


class DurableReplayTest(unittest.TestCase):
    def test_receipts_match_for_many_seeds(self):
        for seed in (0, 1, 2, 5, 7, 13, 23, 42):
            got, want, _, _, _ = _check(
                seed, ("db.primary", "cache.hot", "queue.lead")
            )
            self.assertEqual(got, want, "seed %s 回执分歧" % seed)

    def test_single_resource_replay(self):
        got, want, _, _, _ = _check(11, ("db.primary",))
        self.assertEqual(got, want)

    def test_final_token_and_high_water_after_crashes(self):
        got, want, final, journal, clock = _check(
            3, ("db.primary", "cache.hot"), steps=400
        )
        self.assertEqual(got, want)
        # 再崩一次重放：终局记号与高水位仍只增不减。
        reborn = DurableLeaseKeeper.recover(journal, clock=clock.current)
        self.assertEqual(reborn.stats().last_token, final["last_token"])
        for resource, water in final["high_water"].items():
            self.assertEqual(reborn.high_water(resource), water)

    def test_parallel_event_shape_is_deterministic(self):
        script = [
            ("parallel", "r", "n1", 5.0, "q1", 4),
            ("parallel", "r", "n1", 5.0, "q1", 4),
        ]
        clock = FakeClock()
        journal = MemoryJournal()

        def make_boot(existing):
            if existing is None:
                return DurableLeaseKeeper(clock=clock.current, journal=journal)
            return DurableLeaseKeeper.recover(existing, clock=clock.current)

        got = drive_durable(make_boot, script, clock)
        want, _ = model_durable(script)
        self.assertEqual(got, want)
        first_round = {receipt for receipt in got[0] if receipt is not None}
        self.assertEqual(len(first_round), 1)
        self.assertEqual(got[1], got[0])

    def test_crash_replay_mid_script(self):
        script = [
            ("grantq", "r", "n1", 20.0, "g1"),
            ("sleep", 5.0),
            ("crash",),
            ("renew", "r", "n1", None),
            ("sleep", 21.0),  # 恢复后续到的时刻也已过期
            ("grantq", "r", "n2", 5.0, "g2"),
            ("sleep", 6.0),   # g2 也过期了
            ("crash",),
            ("grantq", "r", "n3", 5.0, "g3"),
            ("crash",),
            ("grantq", "r", "n1", 20.0, "g1"),
        ]
        clock = FakeClock()
        journal = MemoryJournal()

        def make_boot(existing):
            if existing is None:
                return DurableLeaseKeeper(clock=clock.current, journal=journal)
            return DurableLeaseKeeper.recover(existing, clock=clock.current)

        got = drive_durable(make_boot, script, clock)
        want, final = model_durable(script)
        self.assertEqual(got, want)
        self.assertEqual(final["last_token"], 3)
        self.assertEqual(final["high_water"], {"r": 3})

if __name__ == "__main__":
    unittest.main()
