"""DurableLeaseKeeper：幂等发号、日志恢复、续号、高水位、时钟回拨。"""

import threading
import time
import unittest

from leasekeeper.clock import FakeClock
from leasekeeper.durable import DurableLeaseKeeper
from leasekeeper.fence import FenceGuard, StaleFence
from leasekeeper.journal import FileJournal, MemoryJournal
from leasekeeper.keeper import LeaseConflict
import os
import tempfile


class IdempotentGrantTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=1000.0)
        self.keeper = DurableLeaseKeeper(
            clock=self.clock.current, journal=MemoryJournal()
        )

    def test_same_request_id_returns_same_lease(self):
        first = self.keeper.grant("r", "n1", 10.0, request_id="q1")
        retry = self.keeper.grant("r", "n1", 10.0, request_id="q1")
        self.assertIs(first, retry)
        self.assertEqual(self.keeper.stats().grants, 1)

    def test_parallel_same_request_yields_single_grant(self):
        ways = 8
        barrier = threading.Barrier(ways)
        box = [None] * ways

        def attempt(index):
            barrier.wait()
            try:
                box[index] = self.keeper.grant(
                    "hot", "n1", 30.0, request_id="qhot"
                )
            except LeaseConflict:
                box[index] = False

        workers = [threading.Thread(target=attempt, args=(i,)) for i in range(ways)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        leases = [value for value in box if value is not False]
        self.assertEqual(len(leases), ways)
        self.assertEqual({l.token for l in leases}, {1})
        self.assertEqual(self.keeper.stats().grants, 1)

    def test_conflict_is_idempotent_too(self):
        self.keeper.grant("r", "n1", 30.0, request_id="q1")
        for _ in range(2):
            with self.assertRaises(LeaseConflict):
                self.keeper.grant("r", "n2", 30.0, request_id="q2")
        # 撞车结果也幂等：只在首次发放尝试时计一次冲突。
        self.assertEqual(self.keeper.stats().conflicts, 1)
        self.assertEqual(self.keeper.stats().grants, 1)

    def test_request_id_reuse_with_other_params_rejected(self):
        self.keeper.grant("r", "n1", 10.0, request_id="q1")
        with self.assertRaises(ValueError):
            self.keeper.grant("r", "n1", 20.0, request_id="q1")
        with self.assertRaises(ValueError):
            self.keeper.grant("r", "n2", 10.0, request_id="q1")
        with self.assertRaises(ValueError):
            self.keeper.grant("other", "n1", 10.0, request_id="q1")
        self.assertEqual(self.keeper.stats().grants, 1)

    def test_grant_without_request_id_keeps_old_behavior(self):
        first = self.keeper.grant("r", "n1", 10.0)
        self.assertEqual(first.token, 1)
        with self.assertRaises(LeaseConflict):
            self.keeper.grant("r", "n2", 10.0)


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=2000.0)
        self.journal = MemoryJournal()
        self.keeper = DurableLeaseKeeper.recover(
            self.journal, clock=self.clock.current
        )

    def _reboot(self):
        return DurableLeaseKeeper.recover(
            self.journal, clock=self.clock.current
        )

    def test_token_never_resets_after_restart(self):
        self.keeper.grant("a", "n1", 30.0, request_id="g1")
        self.keeper.grant("b", "n2", 30.0, request_id="g2")
        reborn = self._reboot()
        third = reborn.grant("c", "n3", 30.0, request_id="g3")
        self.assertEqual(third.token, 3)
        self.assertEqual(reborn.stats().last_token, 3)

    def test_unreturned_live_lease_resumes_from_log(self):
        lease = self.keeper.grant("a", "n1", 30.0, request_id="g1")
        self.clock.advance(10.0)
        reborn = self._reboot()
        got = reborn.get("a")
        self.assertIsNotNone(got)
        self.assertEqual(got.lease_id, lease.lease_id)
        # 恢复以发号时刻的原始到期为准（续期不进日志）。
        self.assertEqual(got.expires_at, 2030.0)
        renewed = reborn.renew(lease.lease_id, "n1")
        self.assertIsNotNone(renewed)

    def test_expired_at_recovery_is_reclaimed_no_double_active(self):
        self.keeper.grant("a", "n1", 5.0, request_id="g1")
        self.clock.advance(6.0)
        reborn = self._reboot()
        self.assertIsNone(reborn.get("a"))
        new = reborn.grant("a", "n2", 5.0, request_id="g2")
        self.assertEqual(new.token, 2)
        self.assertEqual(reborn.resources(), ["a"])

    def test_recovered_live_lease_blocks_new_grant(self):
        self.keeper.grant("a", "n1", 30.0, request_id="g1")
        reborn = self._reboot()
        with self.assertRaises(LeaseConflict):
            reborn.grant("a", "n2", 30.0, request_id="g2")

    def test_released_lease_not_resurrected(self):
        lease = self.keeper.grant("a", "n1", 30.0, request_id="g1")
        self.keeper.release(lease.lease_id, "n1")
        reborn = self._reboot()
        self.assertIsNone(reborn.get("a"))
        self.assertEqual(reborn.grant("a", "n2", 30.0, request_id="g2").token, 2)

    def test_idempotent_request_replays_same_lease_after_restart(self):
        lease = self.keeper.grant("a", "n1", 30.0, request_id="q1")
        reborn = self._reboot()
        replay = reborn.grant("a", "n1", 30.0, request_id="q1")
        self.assertEqual(replay, lease)

    def test_conflicted_request_still_conflicted_after_restart(self):
        self.keeper.grant("a", "n1", 30.0, request_id="q1")
        with self.assertRaises(LeaseConflict):
            self.keeper.grant("a", "n2", 30.0, request_id="q2")
        reborn = self._reboot()
        with self.assertRaises(LeaseConflict):
            reborn.grant("a", "n2", 30.0, request_id="q2")

    def test_renew_never_written_lease_expires_on_grant_deadline(self):
        lease = self.keeper.grant("a", "n1", 10.0, request_id="q1")
        self.clock.advance(5.0)
        self.keeper.renew(lease.lease_id, "n1")
        self.clock.advance(8.0)  # 续期后还活着，但原始发号已过期
        reborn = self._reboot()
        self.assertIsNone(reborn.get("a"))


class HighWaterTest(unittest.TestCase):
    def test_high_water_covers_all_epochs(self):
        clock = FakeClock()
        journal = MemoryJournal()
        keeper = DurableLeaseKeeper(clock=clock.current, journal=journal)
        keeper.grant("r", "n1", 1.0, request_id="g1")
        clock.advance(2.0)
        keeper.grant("r", "n2", 1.0, request_id="g2")
        clock.advance(2.0)
        keeper.grant("r", "n3", 1.0, request_id="g3")
        reborn = DurableLeaseKeeper.recover(journal, clock=clock.current)
        self.assertEqual(reborn.high_water("r"), 3)
        guard = reborn.seal_guard(FenceGuard())
        guard.check("r", 3)
        with self.assertRaises(StaleFence):
            guard.check("r", 1)

    def test_seal_guard_only_accepts_fence_guard(self):
        keeper = DurableLeaseKeeper(journal=MemoryJournal())
        with self.assertRaises(ValueError):
            keeper.seal_guard(object())


class ClockRollbackTest(unittest.TestCase):
    def test_backward_clock_does_not_extend_lease(self):
        clock = FakeClock(start=9000.0)
        keeper = DurableLeaseKeeper(clock=clock.current, journal=MemoryJournal())
        lease = keeper.grant("r", "n1", 10.0, request_id="g1")
        clock.advance(10.0)
        self.assertIsNone(keeper.get("r"))
        clock.set(9003.0)  # NTP 往回拨 7 秒
        self.assertIsNone(keeper.get("r"))
        self.assertIsNone(keeper.renew(lease.lease_id, "n1"))
        # 已过期不影响幂等：同号重放拿回的仍是原租约快照，不会新发。
        self.assertIs(
            keeper.grant("r", "n1", 10.0, request_id="g1"), lease
        )
        self.assertEqual(keeper.grant("r", "n2", 10.0, request_id="g2").token, 2)


class SweepScaleTest(unittest.TestCase):
    def test_sweep_with_twenty_dead_among_twenty_thousand(self):
        clock = FakeClock()
        keeper = DurableLeaseKeeper(
            clock=clock.current, journal=MemoryJournal()
        )
        for index in range(20):
            keeper.grant("dead-%02d" % index, "n", 5.0,
                         request_id="d%d" % index)
        for index in range(20000):
            keeper.grant("alive-%05d" % index, "n", 3600.0,
                         request_id="a%d" % index)
        clock.advance(6.0)
        start = time.perf_counter()
        dead = keeper.sweep()
        elapsed = time.perf_counter() - start
        self.assertEqual(len(dead), 20)
        self.assertEqual(len(keeper.resources()), 20000)
        self.assertLess(elapsed, 0.05)


class RenewPathTest(unittest.TestCase):
    def test_renew_never_touches_journal(self):
        clock = FakeClock()
        journal = MemoryJournal()
        keeper = DurableLeaseKeeper(clock=clock.current, journal=journal)
        lease = keeper.grant("r", "n1", 30.0, request_id="g1")
        before = len(journal.replay())
        for _ in range(10000):
            keeper.renew(lease.lease_id, "n1")
        self.assertEqual(len(journal.replay()), before)
        self.assertEqual(keeper.stats().renews, 10000)

    def test_renew_storm_throughput(self):
        clock = FakeClock()
        keeper = DurableLeaseKeeper(
            clock=clock.current, journal=MemoryJournal()
        )
        lease = keeper.grant("r", "n1", 30.0, request_id="g1")
        start = time.perf_counter()
        for _ in range(10000):
            keeper.renew(lease.lease_id, "n1")
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0)  # 一万次续期远低于一秒


class FileRecoveryTest(unittest.TestCase):
    def test_recover_from_file_journal_across_objects(self):
        fd, path = tempfile.mkstemp(prefix="lk-fj-")
        os.close(fd)
        os.remove(path)
        try:
            clock = FakeClock(start=3000.0)
            journal = FileJournal(path)
            keeper = DurableLeaseKeeper(clock=clock.current, journal=journal)
            keeper.grant("r", "n1", 30.0, request_id="g1")
            keeper.close()
            reborn = DurableLeaseKeeper.recover(
                FileJournal(path), clock=clock.current
            )
            self.assertEqual(reborn.get("r").token, 1)
            self.assertEqual(
                reborn.grant("r2", "n2", 30.0, request_id="g2").token, 2
            )
            reborn.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
