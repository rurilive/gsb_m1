"""ringbuf 防回归测试：计数、覆盖、顺序、并发安全。"""

import threading
import unittest

from ringbuf import Empty, RingBuffer


class TestCountAndCapacity(unittest.TestCase):
    """现象 1 回归：count 必须始终落在 [0, capacity]。"""

    def test_count_never_exceeds_capacity_on_overwrite(self):
        rb = RingBuffer(3)
        for i in range(100):
            rb.put(i)
            self.assertLessEqual(rb.count(), 3)
        self.assertEqual(rb.count(), 3)

    def test_count_returns_to_zero_after_drain(self):
        rb = RingBuffer(4)
        for i in range(10):
            rb.put(i)
        for _ in range(4):
            rb.get()
        self.assertEqual(rb.count(), 0)
        with self.assertRaises(Empty):
            rb.get()

    def test_overwrite_evicts_oldest(self):
        rb = RingBuffer(3)
        for ch in "abcde":
            rb.put(ch)
        self.assertEqual([rb.get() for _ in range(3)], ["c", "d", "e"])


class TestNoLossNoDuplicate(unittest.TestCase):
    """现象 2/3 回归：不丢消息、不重复消费，含游标回绕边界。"""

    def test_no_loss_across_wrap_boundary(self):
        # 覆盖 head 回绕到最后一格槽位的场景（原缺陷会丢掉该槽位的消息）
        rb = RingBuffer(3)
        for ch in "abcd":
            rb.put(ch)
        self.assertEqual([rb.get() for _ in range(3)], ["b", "c", "d"])

    def test_interleaved_put_get_no_loss(self):
        rb = RingBuffer(5)
        expected = []
        for i in range(200):
            rb.put(i)
            expected.append(i)
            if len(expected) > 5:
                expected.pop(0)  # 缓冲满时最老元素被覆盖
            if i % 2 == 0:
                self.assertEqual(rb.get(), expected.pop(0))
        while True:
            try:
                self.assertEqual(rb.get(), expected.pop(0))
            except Empty:
                break
        self.assertEqual(expected, [])

    def test_concurrent_consumers_no_duplicate(self):
        # 两个消费者竞争同一个元素，必须只有一个拿到
        for _ in range(200):
            rb = RingBuffer(1)
            rb.put("msg")
            got = []
            lock = threading.Lock()

            def consumer():
                try:
                    item = rb.get()
                except Empty:
                    return
                with lock:
                    got.append(item)

            threads = [threading.Thread(target=consumer) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(got, ["msg"])


class TestSnapshot(unittest.TestCase):
    """现象 4 回归：snapshot 必须按写入（逻辑）顺序导出。"""

    def test_snapshot_order_after_wraparound(self):
        rb = RingBuffer(3)
        for ch in "abcde":
            rb.put(ch)
        self.assertEqual(rb.snapshot(), ["c", "d", "e"])

    def test_snapshot_matches_get_order(self):
        rb = RingBuffer(4)
        for i in range(6):
            rb.put(i)
        snap = rb.snapshot()
        self.assertEqual([rb.get() for _ in range(len(snap))], snap)

    def test_snapshot_does_not_mutate(self):
        rb = RingBuffer(2)
        rb.put("x")
        rb.snapshot()
        self.assertEqual(rb.count(), 1)
        self.assertEqual(rb.get(), "x")


class TestConcurrencyStress(unittest.TestCase):
    """多生产者多消费者压力测试：总数守恒、每条消息只被消费一次。"""

    def test_mpmc_exactly_once(self):
        producers, per_producer = 4, 2000
        total = producers * per_producer
        # 容量 >= 总量，保证无覆盖，验证不丢不重
        rb = RingBuffer(total)
        consumed = []
        consumed_lock = threading.Lock()
        producers_done = threading.Event()

        def producer(pid):
            for i in range(per_producer):
                rb.put((pid, i))

        def consumer():
            local = []
            while True:
                try:
                    local.append(rb.get())
                except Empty:
                    if producers_done.is_set() and rb.count() == 0:
                        break
            with consumed_lock:
                consumed.extend(local)

        pthreads = [threading.Thread(target=producer, args=(p,)) for p in range(producers)]
        cthreads = [threading.Thread(target=consumer) for _ in range(3)]
        for t in cthreads:
            t.start()
        for t in pthreads:
            t.start()
        for t in pthreads:
            t.join()
        producers_done.set()
        for t in cthreads:
            t.join()

        self.assertEqual(rb.count(), 0)
        self.assertEqual(len(consumed), total)
        self.assertEqual(sorted(consumed),
                         [(p, i) for p in range(producers) for i in range(per_producer)])

    def test_overwrite_stress_invariants(self):
        # 小容量高并发覆盖：count 永不超过容量，snapshot 长度与 count 一致
        rb = RingBuffer(8)
        stop = threading.Event()
        errors = []

        def producer():
            i = 0
            while not stop.is_set():
                rb.put(i)
                i += 1

        def consumer():
            while not stop.is_set():
                try:
                    rb.get()
                except Empty:
                    pass

        def monitor():
            while not stop.is_set():
                count = rb.count()
                if not 0 <= count <= 8:
                    errors.append(f"count 越界: {count}")
                if not 0 <= len(rb.snapshot()) <= 8:
                    errors.append("snapshot 长度越界")

        threads = ([threading.Thread(target=producer) for _ in range(3)]
                   + [threading.Thread(target=consumer) for _ in range(3)]
                   + [threading.Thread(target=monitor)])
        for t in threads:
            t.start()
        threading.Event().wait(1.0)
        stop.set()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # 静止后 snapshot 长度必须与 count 一致
        self.assertEqual(len(rb.snapshot()), rb.count())


class TestApi(unittest.TestCase):
    def test_invalid_capacity(self):
        with self.assertRaises(ValueError):
            RingBuffer(0)

    def test_empty_raises(self):
        with self.assertRaises(Empty):
            RingBuffer(1).get()


if __name__ == "__main__":
    unittest.main()
