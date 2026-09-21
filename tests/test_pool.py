"""AddressPool 的基线行为，锁定扁平池的分配与归还语义。"""

import unittest

from addrbook.address import parse_addr
from addrbook.errors import (
    AddressInUse,
    AddressNotAllocated,
    OutOfRange,
    PoolExhausted,
)
from addrbook.pool import AddressPool


def a(text):
    return parse_addr(text)


class FromCidrTest(unittest.TestCase):
    def test_default_drops_network_and_broadcast(self):
        pool = AddressPool.from_cidr("10.0.0.0/30")
        self.assertEqual((pool.start, pool.end), (a("10.0.0.1"), a("10.0.0.2")))
        self.assertEqual(pool.capacity, 2)

    def test_usable_only_false_keeps_edges(self):
        pool = AddressPool.from_cidr("10.0.0.0/30", usable_only=False)
        self.assertEqual((pool.start, pool.end), (a("10.0.0.0"), a("10.0.0.3")))
        self.assertEqual(pool.capacity, 4)

    def test_slash_31_and_32_keep_everything(self):
        pool = AddressPool.from_cidr("10.0.0.0/31")
        self.assertEqual((pool.start, pool.end), (a("10.0.0.0"), a("10.0.0.1")))
        self.assertEqual(pool.capacity, 2)
        pool = AddressPool.from_cidr("10.0.0.7/32")
        self.assertEqual(pool.start, pool.end)
        self.assertEqual(pool.capacity, 1)

    def test_slash_24_is_a_classic_dynamic_pool(self):
        pool = AddressPool.from_cidr("192.168.4.0/24")
        self.assertEqual(pool.capacity, 254)
        self.assertEqual((pool.start, pool.end), (a("192.168.4.1"), a("192.168.4.254")))


class RangeTest(unittest.TestCase):
    def test_rejects_bad_ranges(self):
        for start, end in ((5, 4), (-1, 3), (0, (1 << 32))):
            with self.assertRaises(OutOfRange, msg=(start, end)):
                AddressPool(start, end)

    def test_rejects_non_int_bounds(self):
        with self.assertRaises(TypeError):
            AddressPool("10.0.0.0", 12)

    def test_contains_and_is_allocated(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        self.assertTrue(pool.contains(a("10.0.0.1")))
        self.assertTrue(pool.contains(a("10.0.0.6")))
        self.assertFalse(pool.contains(a("10.0.0.0")))
        self.assertFalse(pool.contains(a("10.0.0.7")))
        self.assertFalse(pool.is_allocated(a("10.0.0.1")))


class AllocateTest(unittest.TestCase):
    def test_starts_from_lowest_free(self):
        pool = AddressPool(a("10.0.0.4"), a("10.0.0.7"))
        self.assertEqual(
            [pool.allocate() for _ in range(4)],
            [a("10.0.0.4"), a("10.0.0.5"), a("10.0.0.6"), a("10.0.0.7")],
        )

    def test_released_address_comes_back_first(self):
        pool = AddressPool(a("10.0.0.0"), a("10.0.0.3"))
        first = pool.allocate()
        pool.allocate()
        pool.allocate()
        pool.release(first)
        self.assertEqual(pool.allocate(), first)

    def test_exhausted_pool(self):
        pool = AddressPool(a("10.0.0.0"), a("10.0.0.1"))
        pool.allocate()
        pool.allocate()
        self.assertEqual(pool.free, 0)
        with self.assertRaises(PoolExhausted):
            pool.allocate()

    def test_accounting(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        self.assertEqual((pool.capacity, pool.in_use, pool.free), (6, 0, 6))
        addr = pool.allocate()
        self.assertEqual((pool.in_use, pool.free), (1, 5))
        self.assertTrue(pool.is_allocated(addr))
        self.assertEqual(pool.allocated(), [addr])
        pool.release(addr)
        self.assertEqual((pool.in_use, pool.free), (0, 6))
        self.assertEqual(pool.allocated(), [])

    def test_allocated_is_sorted(self):
        pool = AddressPool(a("10.0.0.0"), a("10.0.0.3"))
        pool.request(a("10.0.0.2"))
        pool.request(a("10.0.0.0"))
        self.assertEqual(pool.allocated(), [a("10.0.0.0"), a("10.0.0.2")])


class RequestTest(unittest.TestCase):
    def test_request_specific_address(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        addr = pool.request(a("10.0.0.4"))
        self.assertEqual(addr, a("10.0.0.4"))
        self.assertTrue(pool.is_allocated(addr))

    def test_request_conflict(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        addr = pool.allocate()
        with self.assertRaises(AddressInUse):
            pool.request(addr)

    def test_request_outside_pool(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        with self.assertRaises(OutOfRange):
            pool.request(a("10.0.0.7"))
        with self.assertRaises(OutOfRange):
            pool.request(a("10.9.9.9"))


class ReleaseTest(unittest.TestCase):
    def test_release_not_allocated(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        addr = pool.allocate()
        with self.assertRaises(AddressNotAllocated):
            pool.release(addr + 1)

    def test_release_twice(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        addr = pool.allocate()
        pool.release(addr)
        with self.assertRaises(AddressNotAllocated):
            pool.release(addr)

    def test_release_outside_pool(self):
        pool = AddressPool.from_cidr("10.0.0.0/29")
        with self.assertRaises(OutOfRange):
            pool.release(a("10.9.9.9"))


if __name__ == "__main__":
    unittest.main()
