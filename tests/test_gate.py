"""gate 现有行为的锁定测试（确定性，不依赖时序）。"""

import threading
import unittest

from tracectx.gate import Gate


class TestGate(unittest.TestCase):
    def test_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            Gate(0)

    def test_active_counts_entries(self):
        g = Gate(2)
        g.enter()
        self.assertEqual(g.active, 1)
        g.enter()
        self.assertEqual(g.active, 2)
        g.leave()
        self.assertEqual(g.active, 1)
        g.leave()
        self.assertEqual(g.active, 0)

    def test_blocks_beyond_limit(self):
        g = Gate(1)
        g.enter()
        box = []
        t = threading.Thread(target=lambda: (g.enter(), box.append(1), g.leave()))
        t.start()
        t.join(0.3)
        self.assertEqual(box, [])  # 名额被主线程占着，进不来
        g.leave()
        t.join(5)
        self.assertEqual(box, [1])

    def test_enter_timeout(self):
        g = Gate(1)
        g.enter()
        with self.assertRaises(TimeoutError):
            g.enter(timeout=0.2)
        g.leave()

    def test_context_manager(self):
        g = Gate(3)
        with g:
            self.assertEqual(g.active, 1)
        self.assertEqual(g.active, 0)

    def test_max_active_property(self):
        self.assertEqual(Gate(4).max_active, 4)


if __name__ == "__main__":
    unittest.main()
