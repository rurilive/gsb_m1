"""引用计数堆现有行为的锁定测试（基线，一字不改）。

锁死改造前的口径：分配对象、登记根与引用、计数归零立即回收，
以及环无法回收这一现状。
"""

import unittest

from gclab import GCError, RefCountHeap


class TestRefCountHeap(unittest.TestCase):
    def test_alloc_increments_ids(self):
        heap = RefCountHeap()
        a = heap.alloc("a")
        b = heap.alloc("b")
        self.assertEqual((a, b), (0, 1))

    def test_has_object(self):
        heap = RefCountHeap()
        oid = heap.alloc()
        self.assertTrue(heap.has_object(oid))
        self.assertFalse(heap.has_object(42))

    def test_payload_roundtrip(self):
        heap = RefCountHeap()
        oid = heap.alloc({"tag": "x"})
        self.assertEqual(heap.payload(oid), {"tag": "x"})

    def test_payload_unknown_raises(self):
        heap = RefCountHeap()
        with self.assertRaises(GCError):
            heap.payload(7)

    def test_objects_in_alloc_order(self):
        heap = RefCountHeap()
        for _ in range(3):
            heap.alloc()
        self.assertEqual(heap.objects(), (0, 1, 2))

    def test_root_add_is_idempotent(self):
        heap = RefCountHeap()
        oid = heap.alloc()
        heap.add_root(oid)
        heap.add_root(oid)
        self.assertEqual(heap.roots(), (oid,))
        self.assertEqual(heap.ref_count(oid), 1)

    def test_root_remove_drops_external_ref(self):
        heap = RefCountHeap()
        oid = heap.alloc()
        heap.add_root(oid)
        heap.remove_root(oid)
        self.assertEqual(heap.roots(), ())
        self.assertFalse(heap.has_object(oid))
        self.assertEqual(heap.collected(), 1)

    def test_add_ref_bumps_count(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        heap.add_root(a)
        heap.add_ref(a, b)
        self.assertEqual(heap.ref_count(b), 1)

    def test_remove_ref_drops_count(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        heap.add_root(a)
        heap.add_root(b)
        heap.add_ref(a, b)
        heap.remove_ref(a, b)
        self.assertEqual(heap.ref_count(b), 1)

    def test_remove_missing_ref_raises(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        heap.add_root(a)
        heap.add_root(b)
        with self.assertRaises(GCError):
            heap.remove_ref(a, b)

    def test_refs_of_dedup_sorted(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        c = heap.alloc()
        heap.add_root(a)
        heap.add_root(b)
        heap.add_root(c)
        heap.add_ref(a, b)
        heap.add_ref(a, b)
        heap.add_ref(a, c)
        self.assertEqual(heap.refs_of(a), (b, c))
        self.assertEqual(heap.ref_count(b), 3)

    def test_drop_to_zero_collects_immediately(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        heap.add_root(a)
        heap.add_ref(a, b)
        heap.remove_ref(a, b)
        self.assertFalse(heap.has_object(b))
        self.assertEqual(heap.collected(), 1)

    def test_collect_cascades(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        c = heap.alloc()
        heap.add_root(a)
        heap.add_ref(a, b)
        heap.add_ref(b, c)
        heap.remove_root(a)
        self.assertEqual(heap.objects(), ())
        self.assertEqual(heap.collected(), 3)

    def test_cycle_leaks(self):
        heap = RefCountHeap()
        a = heap.alloc()
        b = heap.alloc()
        heap.add_root(a)
        heap.add_root(b)
        heap.add_ref(a, b)
        heap.add_ref(b, a)
        heap.remove_root(a)
        heap.remove_root(b)
        self.assertEqual(heap.objects(), (a, b))
        self.assertEqual(heap.collected(), 0)

    def test_self_reference_leaks(self):
        heap = RefCountHeap()
        a = heap.alloc()
        heap.add_root(a)
        heap.add_ref(a, a)
        heap.remove_root(a)
        self.assertTrue(heap.has_object(a))
        self.assertEqual(heap.collected(), 0)

    def test_unknown_object_fails_fast(self):
        heap = RefCountHeap()
        with self.assertRaises(GCError):
            heap.add_root(3)


if __name__ == "__main__":
    unittest.main()
