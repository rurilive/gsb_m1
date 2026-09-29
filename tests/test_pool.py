"""ConnectionPool 现有行为的锁定测试（基线，一字不改）。"""

import threading
import time
import unittest

from connpool.pool import Connection, ConnectionPool


class TestConnection(unittest.TestCase):
    def test_new_connection_is_healthy_and_open(self):
        c = Connection(0)
        self.assertTrue(c.is_healthy())
        self.assertFalse(c.closed)

    def test_mark_unhealthy(self):
        c = Connection(1)
        c.mark_unhealthy()
        self.assertFalse(c.is_healthy())

    def test_close_makes_unhealthy(self):
        c = Connection(2)
        c.close()
        self.assertTrue(c.closed)
        self.assertFalse(c.is_healthy())

    def test_created_at_recorded(self):
        c = Connection(3, created_at=12.5)
        self.assertEqual(c.created_at, 12.5)


class TestConnectionPool(unittest.TestCase):
    def test_acquire_returns_connection(self):
        p = ConnectionPool(2)
        conn = p.acquire()
        self.assertIsInstance(conn, Connection)
        self.assertTrue(conn.is_healthy())
        p.release(conn)

    def test_reuse_idle_connection(self):
        p = ConnectionPool(2)
        a = p.acquire()
        p.release(a)
        b = p.acquire()
        self.assertIs(a, b)
        self.assertEqual(p.stats()["created"], 1)

    def test_created_increases_until_max(self):
        p = ConnectionPool(2)
        a = p.acquire()
        b = p.acquire()
        self.assertIsNot(a, b)
        self.assertEqual(p.stats()["created"], 2)
        self.assertEqual(p.stats()["active"], 2)
        p.release(a)
        p.release(b)

    def test_stats_counts_active_and_idle(self):
        p = ConnectionPool(3)
        a = p.acquire()
        b = p.acquire()
        p.release(a)
        s = p.stats()
        self.assertEqual(s["active"], 1)
        self.assertEqual(s["idle"], 1)
        self.assertEqual(s["created"], 2)
        p.release(b)

    def test_stats_returns_fresh_dict(self):
        p = ConnectionPool(1)
        s = p.stats()
        s["active"] = 99
        self.assertEqual(p.stats()["active"], 0)

    def test_acquire_blocks_at_max_until_release(self):
        p = ConnectionPool(1)
        conn = p.acquire()
        got = []

        def worker():
            got.append(p.acquire())

        t = threading.Thread(target=worker)
        t.start()
        time.sleep(0.1)
        self.assertEqual(got, [])       # 池满，第二个借出被挡住
        p.release(conn)
        t.join(2)
        self.assertFalse(t.is_alive())
        self.assertEqual(len(got), 1)

    def test_release_unknown_raises(self):
        p = ConnectionPool(2)
        with self.assertRaises(ValueError):
            p.release(Connection(99))

    def test_custom_factory_used(self):
        made = []

        def factory():
            conn = Connection(len(made) + 100)
            made.append(conn)
            return conn

        p = ConnectionPool(2, factory=factory)
        conn = p.acquire()
        self.assertEqual(made, [conn])
        p.release(conn)

    def test_clock_is_injectable(self):
        p = ConnectionPool(2, clock=lambda: 7.0)
        conn = p.acquire()
        self.assertEqual(conn.created_at, 7.0)
        p.release(conn)

    def test_invalid_max_size_raises(self):
        with self.assertRaises(ValueError):
            ConnectionPool(0)


if __name__ == "__main__":
    unittest.main()