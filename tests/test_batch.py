"""批量申请、段落合并与批量释放的新行为测试。"""

import threading
import unittest

from batchlease.lease import (
    BatchAborted,
    LeaseManager,
    UnknownMember,
)


class FakeClock:
    """手动推进的假时钟。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


def make_manager(members=None, start=0.0):
    clock = FakeClock(start)
    mgr = LeaseManager(members, clock=clock)
    return mgr, clock


class TestBatchAcquire(unittest.TestCase):
    def test_batch_grants_same_start_to_all_nodes(self):
        mgr, clock = make_manager({"a": 0, "b": 0, "c": 0})
        result = mgr.batch_acquire(["a", "b", "c"], ttl=10.0)
        self.assertEqual(result, {"a": 10.0, "b": 10.0, "c": 10.0})
        for node in ("a", "b", "c"):
            self.assertEqual(mgr.segments(node), [(0.0, 10.0)])

    def test_batch_uses_default_ttl_and_dedupes(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        result = mgr.batch_acquire(["a", "a", "b"])
        self.assertEqual(result, {"a": 30.0, "b": 30.0})
        self.assertEqual(mgr.segments("a"), [(0.0, 30.0)])

    def test_empty_batch_grants_nothing(self):
        mgr, _ = make_manager({"a": 0})
        self.assertEqual(mgr.batch_acquire([]), {})
        self.assertEqual(mgr.segments("a"), [])

    def test_unknown_member_aborts_whole_batch(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        with self.assertRaises(UnknownMember):
            mgr.batch_acquire(["a", "ghost", "b"], ttl=5.0)
        for node in ("a", "b"):
            self.assertEqual(mgr.segments(node), [])
            self.assertIsNone(mgr.expires_at(node))

    def test_bad_ttl_aborts_before_touching_state(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        with self.assertRaises(ValueError):
            mgr.batch_acquire(["a", "b"], ttl=0)
        with self.assertRaises(ValueError):
            mgr.batch_acquire(["a", "b"], ttl=-3)
        for node in ("a", "b"):
            self.assertEqual(mgr.segments(node), [])

    def test_failed_batch_leaves_existing_segments_intact(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        mgr.acquire("a", ttl=7.0)
        with self.assertRaises(UnknownMember):
            mgr.batch_acquire(["a", "ghost"], ttl=5.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 7.0)])

    def test_member_added_during_batch_aborts_it(self):
        mgr, _ = make_manager({"a": 0, "b": 0})

        def add_member(_targets):
            mgr.table.add("latecomer", 0)

        with self.assertRaises(BatchAborted):
            mgr.batch_acquire(["a", "b"], ttl=5.0, during=add_member)
        self.assertEqual(mgr.segments("a"), [])
        self.assertEqual(mgr.segments("b"), [])

    def test_member_removed_during_batch_aborts_it(self):
        mgr, _ = make_manager({"a": 0, "b": 0})

        def remove_b(_targets):
            mgr.table.remove("b")

        with self.assertRaises(BatchAborted):
            mgr.batch_acquire(["a", "b"], ttl=5.0, during=remove_b)
        self.assertEqual(mgr.segments("a"), [])
        self.assertNotIn("b", mgr.table)

    def test_unrelated_member_change_during_batch_still_aborts(self):
        mgr, _ = make_manager({"a": 0, "b": 0})

        def add_unrelated(_targets):
            mgr.table.add("other", 1)

        with self.assertRaises(BatchAborted):
            mgr.batch_acquire(["a"], ttl=5.0, during=add_unrelated)
        self.assertEqual(mgr.segments("a"), [])

    def test_priority_update_during_batch_aborts_it(self):
        mgr, _ = make_manager({"a": 0, "b": 0})

        def reprioritise(_targets):
            mgr.table.add("b", 9)

        with self.assertRaises(BatchAborted):
            mgr.batch_acquire(["a", "b"], ttl=5.0, during=reprioritise)
        self.assertEqual(mgr.segments("a"), [])
        self.assertEqual(mgr.segments("b"), [])

    def test_aborted_batch_blocks_concurrent_table_edit(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        entered = threading.Event()
        release_hook = threading.Event()

        def wait_in_hook(_targets):
            entered.set()
            release_hook.wait(2.0)

        worker = threading.Thread(
            target=lambda: mgr.batch_acquire(["a", "b"], ttl=5.0, during=wait_in_hook)
        )
        worker.start()
        self.assertTrue(entered.wait(2.0))
        done = threading.Event()

        def remove_b():
            mgr.table.remove("b")
            done.set()

        editor = threading.Thread(target=remove_b)
        editor.start()
        self.assertFalse(done.wait(0.2))
        release_hook.set()
        worker.join(2.0)
        editor.join(2.0)
        self.assertFalse(worker.is_alive())
        self.assertFalse(editor.is_alive())


class TestCompact(unittest.TestCase):
    def _seed(self, mgr, intervals):
        for start, end in intervals:
            mgr._segments.setdefault("a", []).append([start, end])

    def test_overlapping_segments_merge_to_latest_end(self):
        mgr, _ = make_manager({"a": 0})
        self._seed(mgr, [(0.0, 10.0), (4.0, 14.0)])
        self.assertEqual(mgr.compact("a"), [(0.0, 14.0)])

    def test_touching_segments_merge(self):
        mgr, _ = make_manager({"a": 0})
        self._seed(mgr, [(0.0, 10.0), (10.0, 20.0)])
        self.assertEqual(mgr.compact("a"), [(0.0, 20.0)])

    def test_merge_keeps_latest_end_even_when_shorter(self):
        mgr, _ = make_manager({"a": 0})
        self._seed(mgr, [(0.0, 20.0), (5.0, 8.0), (10.0, 15.0)])
        self.assertEqual(mgr.compact("a"), [(0.0, 20.0)])

    def test_gap_keeps_segments_apart(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=2.0)
        clock.advance(5.0)
        mgr.acquire("a", ttl=2.0)
        self.assertEqual(mgr.segments("a"), [(0.0, 2.0), (5.0, 7.0)])
        self.assertEqual(mgr.compact("a"), [(0.0, 2.0), (5.0, 7.0)])

    def test_chain_merges_into_one_without_extending(self):
        mgr, _ = make_manager({"a": 0})
        self._seed(mgr, [(0.0, 4.0), (4.0, 8.0), (7.0, 12.0)])
        self.assertEqual(mgr.compact("a"), [(0.0, 12.0)])

    def test_expired_segments_still_merge(self):
        mgr, clock = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        clock.advance(5.0)
        mgr.acquire("a", ttl=5.0)
        clock.advance(5.0)
        self.assertFalse(mgr.held("a"))
        self.assertEqual(mgr.compact("a"), [(0.0, 10.0)])
        self.assertEqual(mgr.expires_at("a"), 10.0)

    def test_compact_empty_is_empty(self):
        mgr, _ = make_manager({"a": 0})
        self.assertEqual(mgr.compact("a"), [])

    def test_compact_unknown_member_raises(self):
        mgr, _ = make_manager({"a": 0})
        with self.assertRaises(UnknownMember):
            mgr.compact("ghost")


class TestBatchRelease(unittest.TestCase):
    def test_partial_success_is_reported_by_bucket(self):
        mgr, _ = make_manager({"a": 0, "b": 0, "c": 0})
        mgr.acquire("a", ttl=5.0)
        mgr.acquire("c", ttl=5.0)
        result = mgr.batch_release(["a", "b", "ghost", "c"])
        self.assertEqual(result.released, ["a", "c"])
        self.assertEqual(result.empty, ["b"])
        self.assertEqual(result.unknown, ["ghost"])
        self.assertEqual(result.failures, ["ghost"])

    def test_already_released_never_rolls_back(self):
        mgr, _ = make_manager({"a": 0, "b": 0, "c": 0})
        mgr.acquire("a", ttl=5.0)
        mgr.acquire("b", ttl=5.0)
        result = mgr.batch_release(["a", "ghost", "b"])
        self.assertEqual(result.released, ["a", "b"])
        self.assertEqual(result.unknown, ["ghost"])
        for node in ("a", "b"):
            self.assertEqual(mgr.segments(node), [])

    def test_empty_and_unknown_nodes_do_not_stop_the_batch(self):
        mgr, _ = make_manager({"a": 0, "b": 0})
        mgr.acquire("b", ttl=5.0)
        result = mgr.batch_release(["ghost1", "a", "ghost2", "b"])
        self.assertEqual(result.unknown, ["ghost1", "ghost2"])
        self.assertEqual(result.empty, ["a"])
        self.assertEqual(result.released, ["b"])

    def test_repeated_release_is_idempotent_and_deduped(self):
        mgr, _ = make_manager({"a": 0})
        mgr.acquire("a", ttl=5.0)
        first = mgr.batch_release(["a"])
        self.assertEqual(first.released, ["a"])
        second = mgr.batch_release(["a", "a"])
        self.assertEqual(second.released, [])
        self.assertEqual(second.empty, ["a"])

    def test_empty_batch_release_is_all_empty_result(self):
        mgr, _ = make_manager({"a": 0})
        result = mgr.batch_release([])
        self.assertEqual((result.released, result.empty, result.unknown), ([], [], []))


if __name__ == "__main__":
    unittest.main()
