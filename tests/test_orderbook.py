"""FlatBook 现有行为的锁定测试。

只覆盖朴素实现眼下已经具备的能力：追加订单、线性扫描求最优价、
按价位累加数量、按订单号撤销、以及非法入参的报错口径。
新增行为（档位聚合、有序价格结构、撮合、复杂度计数等）另建测试文件，
本文件一个字都不许改，且必须保持全绿。
"""

import unittest

from booklib.orderbook import BUY, SELL, BookError, FlatBook


class TestAdd(unittest.TestCase):
    def test_add_returns_increasing_ids(self):
        b = FlatBook()
        first = b.add(BUY, 100, 5)
        second = b.add(BUY, 101, 3)
        self.assertLess(first, second)

    def test_len_counts_both_sides(self):
        b = FlatBook()
        b.add(BUY, 100, 5)
        b.add(SELL, 110, 7)
        self.assertEqual(len(b), 2)

    def test_add_unknown_side_raises(self):
        b = FlatBook()
        with self.assertRaises(BookError):
            b.add("hold", 100, 5)

    def test_add_negative_price_raises(self):
        b = FlatBook()
        with self.assertRaises(BookError):
            b.add(BUY, -1, 5)

    def test_add_non_positive_qty_raises(self):
        b = FlatBook()
        with self.assertRaises(BookError):
            b.add(BUY, 100, 0)
        with self.assertRaises(BookError):
            b.add(BUY, 100, -3)


class TestBestPrice(unittest.TestCase):
    def test_best_bid_empty_is_none(self):
        self.assertIsNone(FlatBook().best_bid())

    def test_best_ask_empty_is_none(self):
        self.assertIsNone(FlatBook().best_ask())

    def test_best_bid_is_highest(self):
        b = FlatBook()
        b.add(BUY, 100, 5)
        b.add(BUY, 103, 1)
        b.add(BUY, 101, 2)
        self.assertEqual(b.best_bid(), 103)

    def test_best_ask_is_lowest(self):
        b = FlatBook()
        b.add(SELL, 110, 5)
        b.add(SELL, 107, 1)
        b.add(SELL, 109, 2)
        self.assertEqual(b.best_ask(), 107)


class TestQtyAt(unittest.TestCase):
    def test_qty_at_sums_same_price(self):
        b = FlatBook()
        b.add(BUY, 100, 5)
        b.add(BUY, 100, 7)
        b.add(BUY, 99, 2)
        self.assertEqual(b.qty_at(BUY, 100), 12)

    def test_qty_at_absent_price_is_zero(self):
        b = FlatBook()
        b.add(SELL, 110, 5)
        self.assertEqual(b.qty_at(SELL, 108), 0)

    def test_qty_at_unknown_side_raises(self):
        b = FlatBook()
        with self.assertRaises(BookError):
            b.qty_at("hold", 100)


class TestCancel(unittest.TestCase):
    def test_cancel_removes_and_returns_true(self):
        b = FlatBook()
        oid = b.add(BUY, 100, 5)
        b.add(BUY, 100, 7)
        self.assertTrue(b.cancel(oid))
        self.assertEqual(b.qty_at(BUY, 100), 7)

    def test_cancel_missing_returns_false(self):
        b = FlatBook()
        b.add(BUY, 100, 5)
        self.assertFalse(b.cancel(999))

    def test_cancel_updates_best_price(self):
        b = FlatBook()
        top = b.add(BUY, 103, 1)
        b.add(BUY, 101, 2)
        b.cancel(top)
        self.assertEqual(b.best_bid(), 101)


class TestOrders(unittest.TestCase):
    def test_orders_snapshot_in_insertion_order(self):
        b = FlatBook()
        b.add(BUY, 100, 5)
        b.add(BUY, 101, 6)
        snapshot = b.orders(BUY)
        self.assertEqual([(p, q) for _, p, q in snapshot], [(100, 5), (101, 6)])

    def test_book_error_is_exception_subclass(self):
        self.assertTrue(issubclass(BookError, Exception))


if __name__ == "__main__":
    unittest.main()
