"""RingBuffer 单线程语义防回归测试。"""

import collections
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ringbuf import Empty, RingBuffer


class TestRingBuffer(unittest.TestCase):
    def test_fifo_without_overwrite(self):
        rb = RingBuffer(3)
        for ch in "abc":
            rb.put(ch)
        self.assertEqual(rb.count(), 3)
        self.assertEqual(rb.snapshot(), ["a", "b", "c"])
        self.assertEqual([rb.get() for _ in range(3)], ["a", "b", "c"])
        self.assertEqual(rb.count(), 0)
        self.assertEqual(rb.snapshot(), [])

    def test_overwrite_oldest(self):
        rb = RingBuffer(3)
        for ch in "abcde":
            rb.put(ch)
        self.assertEqual(rb.count(), 3)
        self.assertEqual(rb.snapshot(), ["c", "d", "e"])
        self.assertEqual([rb.get() for _ in range(3)], ["c", "d", "e"])

    def test_count_never_exceeds_capacity(self):
        rb = RingBuffer(4)
        for i in range(1000):
            rb.put(i)
            self.assertLessEqual(rb.count(), 4)
            self.assertGreaterEqual(rb.count(), 0)
        self.assertEqual(rb.count(), 4)

    def test_empty_raises(self):
        rb = RingBuffer(2)
        with self.assertRaises(Empty):
            rb.get()
        rb.put(1)
        rb.get()
        with self.assertRaises(Empty):
            rb.get()

    def test_invalid_capacity(self):
        with self.assertRaises(ValueError):
            RingBuffer(0)
        with self.assertRaises(ValueError):
            RingBuffer(-3)

    def test_capacity_one(self):
        rb = RingBuffer(1)
        self.assertEqual(rb.snapshot(), [])
        rb.put("a")
        self.assertEqual(rb.snapshot(), ["a"])
        rb.put("b")
        self.assertEqual(rb.count(), 1)
        self.assertEqual(rb.snapshot(), ["b"])
        self.assertEqual(rb.get(), "b")
        with self.assertRaises(Empty):
            rb.get()

    def test_last_physical_slot_not_skipped(self):
        # 回归：head 回绕条件曾为 >= capacity，使物理最后一个槽位
        # （下标 capacity）写入后永远读不到，表现为“缓冲没满但少消息”。
        rb = RingBuffer(3)
        rb.put("a")
        rb.put("b")
        rb.put("c")
        rb.get()
        rb.get()
        rb.put("d")
        self.assertEqual(rb.count(), 2)
        self.assertEqual(rb.snapshot(), ["c", "d"])
        self.assertEqual([rb.get(), rb.get()], ["c", "d"])

    def test_snapshot_order_after_physical_wrap(self):
        # head 回绕到尾部后，snapshot 必须跨末尾拼接，保持逻辑顺序。
        rb = RingBuffer(4)
        for x in range(9):  # 触发多次回绕与覆盖
            rb.put(x)
        self.assertEqual(rb.snapshot(), [5, 6, 7, 8])
        rb.get()
        rb.get()
        rb.put(9)
        self.assertEqual(rb.snapshot(), [7, 8, 9])

    def test_snapshot_independent_copy(self):
        rb = RingBuffer(3)
        for ch in "abc":
            rb.put(ch)
        snap = rb.snapshot()
        snap[0] = "X"
        snap.append("Y")
        self.assertEqual(rb.snapshot(), ["a", "b", "c"])
        self.assertEqual(rb.count(), 3)

    def test_matches_deque_model(self):
        # 用 deque(maxlen=capacity) 作为参考模型，随机操作序列下
        # count / snapshot / get 的结果必须与模型完全一致。
        for seed in range(200):
            rng = random.Random(seed)
            cap = rng.randint(1, 8)
            rb = RingBuffer(cap)
            model = collections.deque(maxlen=cap)
            for _ in range(300):
                if rng.random() < 0.6:
                    item = rng.randint(0, 1_000_000)
                    rb.put(item)
                    model.append(item)
                elif model:
                    self.assertEqual(rb.get(), model.popleft())
                else:
                    with self.assertRaises(Empty):
                        rb.get()
                self.assertEqual(rb.count(), len(model))
                self.assertEqual(rb.snapshot(), list(model))
            drained = []
            try:
                while True:
                    drained.append(rb.get())
            except Empty:
                pass
            self.assertEqual(drained, list(model))
            self.assertEqual(rb.count(), 0)


if __name__ == "__main__":
    unittest.main()
