"""BorrowPool 现有行为的锁定测试。"""

import unittest

from slabbin.pool import Block, BorrowPool


class TestBlock(unittest.TestCase):
    def test_block_has_bid(self):
        b = Block(0)
        self.assertEqual(b.bid, 0)

    def test_block_payload_default_none(self):
        b = Block(1)
        self.assertIsNone(b.payload)

    def test_block_payload_kept(self):
        b = Block(2, payload={"k": 1})
        self.assertEqual(b.payload, {"k": 1})


class TestBorrowPool(unittest.TestCase):
    def test_borrow_returns_block(self):
        p = BorrowPool()
        self.assertIsInstance(p.borrow(), Block)

    def test_borrow_empty_creates_new(self):
        p = BorrowPool()
        p.borrow()
        self.assertEqual(p.created, 1)

    def test_give_back_then_borrow_reuses(self):
        p = BorrowPool()
        a = p.borrow()
        p.give_back(a)
        b = p.borrow()
        self.assertIs(a, b)
        self.assertEqual(p.created, 1)

    def test_created_increases_per_new_block(self):
        p = BorrowPool()
        a = p.borrow()
        b = p.borrow()
        self.assertIsNot(a, b)
        self.assertEqual(p.created, 2)

    def test_idle_tracks_give_back(self):
        p = BorrowPool()
        a = p.borrow()
        b = p.borrow()
        p.give_back(a)
        p.give_back(b)
        self.assertEqual(p.idle, 2)

    def test_custom_factory_used(self):
        made = []

        def factory():
            block = Block(len(made) + 100)
            made.append(block)
            return block

        p = BorrowPool(factory=factory)
        block = p.borrow()
        self.assertEqual(made, [block])
        self.assertEqual(block.bid, 100)


if __name__ == "__main__":
    unittest.main()
