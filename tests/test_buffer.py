"""Buffer 的既有行为锁定。"""

import unittest

from bufpool.buffer import Buffer


class BufferTest(unittest.TestCase):
    def test_size_capacity_and_len(self):
        buf = Buffer(bytearray(8), 5, serial=3)
        self.assertEqual(buf.size, 5)
        self.assertEqual(buf.capacity, 8)
        self.assertEqual(len(buf), 5)
        self.assertEqual(buf.serial, 3)

    def test_view_spans_the_whole_capacity_and_is_writable(self):
        buf = Buffer(bytearray(4), 2)
        view = buf.view()
        self.assertEqual(len(view), 4)
        view[:] = b"abcd"
        self.assertEqual(bytes(buf.view()), b"abcd")

    def test_zero_clears_the_whole_capacity(self):
        buf = Buffer(bytearray(b"secret-secret"), 6)
        buf.zero()
        self.assertEqual(bytes(buf.view()), b"\x00" * 13)
        self.assertEqual(buf.size, 6)

    def test_backing_store_must_be_bytearray(self):
        with self.assertRaises(TypeError):
            Buffer(bytes(4), 4)

    def test_repr_carries_serial_size_capacity(self):
        text = repr(Buffer(bytearray(16), 9, serial=7))
        self.assertIn("serial=7", text)
        self.assertIn("size=9", text)
        self.assertIn("capacity=16", text)


if __name__ == "__main__":
    unittest.main()
