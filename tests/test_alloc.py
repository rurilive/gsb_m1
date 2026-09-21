"""朴素分配器的既有行为锁定。"""

import threading
import unittest

from bufpool.alloc import Allocator
from bufpool.errors import InvalidSize, UnknownBuffer


class FakeClock:
    """手动推进的时钟，单位秒。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now += delta
        return self.now


class AllocatorTest(unittest.TestCase):
    def test_acquire_returns_zeroed_buffer_of_requested_size(self):
        alloc = Allocator()
        buf = alloc.acquire(300)
        self.assertEqual(buf.size, 300)
        self.assertEqual(buf.capacity, 300)
        self.assertEqual(bytes(buf.view()), b"\x00" * 300)

    def test_release_unknown_buffer_raises(self):
        alloc = Allocator()
        other = Allocator()
        stranger = other.acquire(64)
        with self.assertRaises(UnknownBuffer):
            alloc.release(stranger)

    def test_release_twice_raises(self):
        alloc = Allocator()
        buf = alloc.acquire(64)
        alloc.release(buf)
        with self.assertRaises(UnknownBuffer):
            alloc.release(buf)

    def test_invalid_size_raises_before_any_state_change(self):
        alloc = Allocator()
        for bad in (0, -8, 2.5, "1024", True):
            with self.assertRaises(InvalidSize):
                alloc.acquire(bad)
        self.assertEqual(alloc.stats()["acquisitions"], 0)

    def test_stats_track_counts_bytes_and_peak(self):
        alloc = Allocator()
        first = alloc.acquire(100)
        second = alloc.acquire(70000)
        self.assertEqual(alloc.stats()["live"], 2)
        self.assertEqual(alloc.stats()["peak_live"], 2)
        self.assertEqual(alloc.stats()["bytes_acquired"], 70100)
        self.assertEqual(alloc.stats()["tier_counts"], {256: 1, "oversize": 1})
        alloc.release(first)
        alloc.release(second)
        snap = alloc.stats()
        self.assertEqual(snap["acquisitions"], 2)
        self.assertEqual(snap["releases"], 2)
        self.assertEqual(snap["live"], 0)
        self.assertEqual(snap["peak_live"], 2)

    def test_outstanding_reports_age_from_injected_clock(self):
        clock = FakeClock(100.0)
        alloc = Allocator(clock=clock)
        first = alloc.acquire(256)
        clock.advance(3.0)
        second = alloc.acquire(256)
        clock.advance(2.0)
        rows = alloc.outstanding()
        self.assertEqual(rows, [(first.serial, 256, 5.0), (second.serial, 256, 2.0)])
        alloc.release(first)
        alloc.release(second)
        self.assertEqual(alloc.outstanding(), [])

    def test_concurrent_acquire_release_stays_consistent(self):
        alloc = Allocator()
        sizes = (100, 3000, 70000)
        errors = []
        barrier = threading.Barrier(8)

        def worker(seed):
            try:
                barrier.wait(timeout=5)
                for step in range(200):
                    size = sizes[(seed + step) % len(sizes)]
                    buf = alloc.acquire(size)
                    buf.view()[:8] = bytes([seed]) * 8
                    assert bytes(buf.view()[:8]) == bytes([seed]) * 8
                    alloc.release(buf)
            except Exception as exc:  # pragma: no cover - 失败时收集原因
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(errors, [])
        snap = alloc.stats()
        self.assertEqual(snap["acquisitions"], 1600)
        self.assertEqual(snap["releases"], 1600)
        self.assertEqual(snap["live"], 0)


if __name__ == "__main__":
    unittest.main()
