"""BumpAlloc 现有行为的锁定测试。"""

import unittest

from chunkheap.alloc import AllocError, BumpAlloc, HeapError


class TestBumpAlloc(unittest.TestCase):
    def test_alloc_returns_data_offset_after_header(self):
        h = BumpAlloc(1024)
        self.assertEqual(h.alloc(32), h.HEADER)

    def test_alloc_advances_by_header_plus_size(self):
        h = BumpAlloc(1024)
        first = h.alloc(32)
        second = h.alloc(16)
        self.assertEqual(second, first + h.HEADER + 32)
        self.assertEqual(h.used, 2 * h.HEADER + 48)

    def test_capacity_kept(self):
        h = BumpAlloc(256)
        self.assertEqual(h.capacity, 256)

    def test_alloc_beyond_capacity_raises(self):
        h = BumpAlloc(64)
        with self.assertRaises(AllocError):
            h.alloc(128)

    def test_alloc_fills_exactly_to_capacity(self):
        h = BumpAlloc(48)
        self.assertEqual(h.alloc(32), h.HEADER)
        self.assertEqual(h.used, 48)

    def test_negative_capacity_raises(self):
        with self.assertRaises(AllocError):
            BumpAlloc(-1)

    def test_negative_size_raises(self):
        h = BumpAlloc(64)
        with self.assertRaises(AllocError):
            h.alloc(-1)

    def test_free_is_noop(self):
        h = BumpAlloc(256)
        offset = h.alloc(32)
        before = h.used
        h.free(offset)
        self.assertEqual(h.used, before)

    def test_free_does_not_reuse(self):
        h = BumpAlloc(256)
        first = h.alloc(32)
        h.free(first)
        second = h.alloc(32)
        self.assertNotEqual(second, first)

    def test_message_reports_state(self):
        h = BumpAlloc(256)
        h.alloc(16)
        self.assertIn("bump", h.message())

    def test_alloc_error_is_heap_error(self):
        self.assertTrue(issubclass(AllocError, HeapError))


if __name__ == "__main__":
    unittest.main()
