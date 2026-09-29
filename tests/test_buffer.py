"""UnboundedBuffer 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：put 永远成功并把元素追加到队尾、get 从队首
取出、peek 只看不取、空缓冲上的 get 与 peek 返回 (False, None)、长度与空判断、
clear 清空，以及先进先出次序。新增行为（有界容量、高低水位与背压信号、拒绝与
丢弃策略、唤醒顺序、计量与边界校验）另建测试文件，不改动本文件。
"""

import unittest

from pushbuf.buffer import UnboundedBuffer


class TestPut(unittest.TestCase):
    def test_put_returns_item(self):
        buf = UnboundedBuffer()
        self.assertEqual(buf.put("a"), "a")

    def test_put_always_succeeds(self):
        buf = UnboundedBuffer()
        for i in range(100):
            buf.put(i)
        self.assertEqual(len(buf), 100)

    def test_put_appends_to_tail(self):
        buf = UnboundedBuffer()
        buf.put("a")
        buf.put("b")
        self.assertEqual(buf.peek(), (True, "a"))


class TestGet(unittest.TestCase):
    def test_get_empty_returns_false_none(self):
        buf = UnboundedBuffer()
        self.assertEqual(buf.get(), (False, None))

    def test_get_fifo_order(self):
        buf = UnboundedBuffer()
        buf.put("a")
        buf.put("b")
        buf.put("c")
        self.assertEqual(buf.get(), (True, "a"))
        self.assertEqual(buf.get(), (True, "b"))
        self.assertEqual(buf.get(), (True, "c"))

    def test_get_drains_then_empty(self):
        buf = UnboundedBuffer()
        buf.put(1)
        self.assertEqual(buf.get(), (True, 1))
        self.assertEqual(buf.get(), (False, None))


class TestPeek(unittest.TestCase):
    def test_peek_empty_returns_false_none(self):
        buf = UnboundedBuffer()
        self.assertEqual(buf.peek(), (False, None))

    def test_peek_does_not_remove(self):
        buf = UnboundedBuffer()
        buf.put("a")
        self.assertEqual(buf.peek(), (True, "a"))
        self.assertEqual(len(buf), 1)


class TestLengthAndClear(unittest.TestCase):
    def test_empty_true_when_new(self):
        buf = UnboundedBuffer()
        self.assertTrue(buf.empty())

    def test_empty_false_after_put(self):
        buf = UnboundedBuffer()
        buf.put("a")
        self.assertFalse(buf.empty())

    def test_len_tracks_puts_and_gets(self):
        buf = UnboundedBuffer()
        buf.put("a")
        buf.put("b")
        self.assertEqual(len(buf), 2)
        buf.get()
        self.assertEqual(len(buf), 1)

    def test_clear_removes_all(self):
        buf = UnboundedBuffer()
        buf.put("a")
        buf.put("b")
        buf.clear()
        self.assertTrue(buf.empty())
        self.assertEqual(len(buf), 0)
        self.assertEqual(buf.get(), (False, None))


if __name__ == "__main__":
    unittest.main()
