"""脚本对拍：生成确定性、真实现与纯模型逐条一致，基线不许动。"""

import unittest

from leasekeeper.clock import FakeClock
from leasekeeper.keeper import LeaseKeeper
from leasekeeper.script import as_tuple, drive, make_script, model_run


class MakeScriptTest(unittest.TestCase):
    def test_same_seed_same_script(self):
        self.assertEqual(
            make_script(seed=3, steps=50), make_script(seed=3, steps=50)
        )

    def test_different_seed_diverges(self):
        self.assertNotEqual(
            make_script(seed=3, steps=50), make_script(seed=4, steps=50)
        )

    def test_script_is_event_tuples(self):
        script = make_script(seed=1, resources=("a", "b"), steps=30)
        self.assertEqual(len(script), 30)
        for event in script:
            self.assertIn(event[0], ("grant", "renew", "release", "sleep"))


class ReplayTest(unittest.TestCase):
    def _check(self, seed, resources):
        script = make_script(seed=seed, resources=resources, steps=200)
        clock = FakeClock()
        keeper = LeaseKeeper(clock=clock.current)
        got = [as_tuple(r) for r in drive(keeper, script, clock)]
        want_receipts, final = model_run(script)
        want = [as_tuple(r) for r in want_receipts]
        self.assertEqual(got, want)
        self.assertEqual(keeper.stats().grants, final["grants"])
        holders = {}
        for resource in final["holders"]:
            lease = keeper.get(resource)
            holders[resource] = lease.holder if lease is not None else None
        self.assertEqual(holders, final["holders"])

    def test_replay_matches_model_single_resource(self):
        self._check(7, ("db.primary",))

    def test_replay_matches_model_many_resources(self):
        self._check(11, ("db.primary", "cache.hot", "queue.lead"))

    def test_replay_matches_model_for_more_seeds(self):
        for seed in (1, 2, 5, 23):
            self._check(seed, ("r1", "r2"))


class ReceiptTest(unittest.TestCase):
    def test_sleep_receipts_track_clock(self):
        script = [("sleep", 2.5), ("sleep", 1.0)]
        clock = FakeClock()
        receipts = drive(LeaseKeeper(clock=clock.current), script, clock)
        self.assertEqual(receipts, [2.5, 3.5])

    def test_conflict_receipt_is_none(self):
        script = [("grant", "r", "n1", 5.0), ("grant", "r", "n2", 5.0)]
        clock = FakeClock()
        receipts = drive(LeaseKeeper(clock=clock.current), script, clock)
        self.assertEqual(as_tuple(receipts[0])[:3], ("L000001", "r", "n1"))
        self.assertIsNone(receipts[1])

    def test_release_receipts_true_then_false(self):
        script = [
            ("grant", "r", "n1", 5.0),
            ("release", "r", "n1"),
            ("release", "r", "n1"),
        ]
        clock = FakeClock()
        receipts = drive(LeaseKeeper(clock=clock.current), script, clock)
        self.assertEqual(receipts[1], True)
        self.assertEqual(receipts[2], False)

    def test_renew_receipt_none_after_expiry(self):
        script = [("grant", "r", "n1", 5.0), ("sleep", 6.0),
                  ("renew", "r", "n1", None)]
        clock = FakeClock()
        receipts = drive(LeaseKeeper(clock=clock.current), script, clock)
        self.assertIsNone(receipts[2])


class ModelTest(unittest.TestCase):
    def test_model_final_holders_after_expiry(self):
        script = [("grant", "r", "n1", 5.0), ("sleep", 6.0)]
        _, final = model_run(script)
        self.assertIsNone(final["holders"]["r"])
        self.assertEqual(final["grants"], 1)

    def test_model_counts_only_successful_grants(self):
        script = [("grant", "r", "n1", 5.0), ("grant", "r", "n2", 5.0)]
        _, final = model_run(script)
        self.assertEqual(final["grants"], 1)
        self.assertEqual(final["holders"]["r"], "n1")

    def test_as_tuple_flattens_both_sides(self):
        clock = FakeClock()
        keeper = LeaseKeeper(clock=clock.current)
        lease = keeper.grant("r", "n1", 5.0)
        receipts, _ = model_run([("grant", "r", "n1", 5.0)])
        self.assertEqual(as_tuple(lease), as_tuple(receipts[0]))


if __name__ == "__main__":
    unittest.main()
