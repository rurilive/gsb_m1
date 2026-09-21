"""ExactCounter 现有行为的锁定测试。"""

import threading
import unittest

from dedupkit.exact import ExactCounter


class TestExactCounter(unittest.TestCase):
    def test_first_add_returns_true_repeat_returns_false(self):
        counter = ExactCounter()
        self.assertTrue(counter.add("u1"))
        self.assertFalse(counter.add("u1"))

    def test_count_counts_distinct_keys_only(self):
        counter = ExactCounter()
        for key in ["u1", "u2", "u1", "u3", "u2", "u1"]:
            counter.add(key)
        self.assertEqual(counter.count(), 3)

    def test_empty_counter_counts_zero(self):
        self.assertEqual(ExactCounter().count(), 0)

    def test_keys_follow_set_equality(self):
        counter = ExactCounter()
        counter.add(1)
        counter.add(1.0)  # 与 1 相等，算同一个 key
        self.assertEqual(counter.count(), 1)
        counter.add(True)  # True 与 1 也相等
        self.assertEqual(counter.count(), 1)
        counter.add("1")
        counter.add(b"1")
        counter.add((1,))
        self.assertEqual(counter.count(), 4)

    def test_accepts_hashable_key_types(self):
        counter = ExactCounter()
        counter.add("id-1")
        counter.add(b"id-1")
        counter.add((1, 2))
        counter.add(None)
        self.assertEqual(counter.count(), 4)

    def test_keys_snapshot_is_a_copy(self):
        counter = ExactCounter()
        counter.add("u1")
        snapshot = counter.keys()
        counter.add("u2")
        self.assertEqual(len(snapshot), 1)
        self.assertIn("u1", snapshot)
        self.assertEqual(len(counter.keys()), 2)

    def test_contains_reflects_added_keys(self):
        counter = ExactCounter()
        counter.add("u1")
        self.assertIn("u1", counter)
        self.assertNotIn("u2", counter)

    def test_contains_does_not_change_count(self):
        counter = ExactCounter()
        counter.add("u1")
        self.assertNotIn("nope", counter)
        self.assertEqual(counter.count(), 1)

    def test_reset_clears_state(self):
        counter = ExactCounter()
        counter.add("u1")
        counter.add("u2")
        counter.reset()
        self.assertEqual(counter.count(), 0)
        self.assertNotIn("u1", counter)
        self.assertTrue(counter.add("u1"))

    def test_large_sequential_input_stays_exact(self):
        counter = ExactCounter()
        for i in range(5000):
            self.assertTrue(counter.add(i))
        for i in range(5000):
            self.assertFalse(counter.add(i))
        self.assertEqual(counter.count(), 5000)

    def test_unhashable_key_raises(self):
        counter = ExactCounter()
        with self.assertRaises(TypeError):
            counter.add(["not", "hashable"])

    def test_concurrent_adds_do_not_lose_keys(self):
        counter = ExactCounter()

        def worker(base):
            for i in range(200):
                counter.add((base, i))

        threads = [threading.Thread(target=worker, args=(b,)) for b in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(counter.count(), 800)


if __name__ == "__main__":
    unittest.main()
