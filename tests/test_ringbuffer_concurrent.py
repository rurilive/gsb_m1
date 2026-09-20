"""RingBuffer 多生产者/多消费者并发防回归测试。"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ringbuf import Empty, RingBuffer


def install_head_advance_blocker(rb):
    """在 head 推进前插入阻塞点，用于确定性暴露 get 临界区外的竞态。

    兼容旧实现（_advance_head）与修复后实现（_advance(cursor)）。
    返回 (released, proceed)：released 在 head 即将推进时置位，
    测试在观察到 released 后放行 proceed。
    """
    released = threading.Event()
    proceed = threading.Event()
    if hasattr(rb, "_advance_head"):  # 旧实现
        def blocked_advance():
            released.set()
            proceed.wait(timeout=10)
        rb._advance_head = blocked_advance
    else:  # 修复后实现：只阻塞 head 的推进，不影响 tail
        original_advance = rb._advance

        def blocked_advance(cursor):
            if cursor == rb._head:
                released.set()
                proceed.wait(timeout=10)
            return original_advance(cursor)

        rb._advance = blocked_advance
    return released, proceed


class TestTwoConsumersOneItem(unittest.TestCase):
    def test_single_item_delivered_once(self):
        # 回归：旧实现在锁内只取值，head 推进与 count 递减都在锁外，
        # 两个消费者可同时读到同一条消息。
        rb = RingBuffer(2)
        rb.put("only-msg")
        released, proceed = install_head_advance_blocker(rb)

        results = []

        def consume():
            try:
                results.append(("ok", rb.get()))
            except Empty:
                results.append(("empty", None))

        t1 = threading.Thread(target=consume)
        t2 = threading.Thread(target=consume)
        t1.start()
        self.assertTrue(released.wait(timeout=5), "t1 未进入 head 推进阶段")
        t2.start()
        time.sleep(0.2)  # 让 t2 在 t1 完成前完整执行一次 get
        proceed.set()
        t1.join(timeout=5)
        t2.join(timeout=5)
        self.assertFalse(t1.is_alive() or t2.is_alive())
        self.assertEqual(sorted(results), [("empty", None), ("ok", "only-msg")])
        self.assertEqual(rb.count(), 0)


class TestMpmcNoOverwrite(unittest.TestCase):
    def test_each_message_consumed_exactly_once(self):
        # 不触发覆盖：容量 >= 消息总数，所有消息必须恰好被消费一次，
        # 缓冲最终为空，且任何时刻 count 都在 [0, capacity]。
        producers = 4
        per_producer = 500
        total = producers * per_producer
        rb = RingBuffer(total)

        violations = []
        real_count = threading.Lock()
        stop = threading.Event()

        def watch_count():
            while not stop.wait(timeout=0.001):
                value = rb.count()
                if value < 0 or value > total:
                    with real_count:
                        violations.append(value)

        def produce(producer_id):
            start.wait()
            for seq in range(per_producer):
                rb.put((producer_id, seq))

        consumed = []
        consumed_lock = threading.Lock()
        start = threading.Barrier(producers + 2)

        def consume():
            start.wait()
            while True:
                try:
                    item = rb.get()
                except Empty:
                    if producers_done.is_set():
                        break
                    continue
                with consumed_lock:
                    consumed.append(item)

        producers_done = threading.Event()

        def run_producers():
            threads = [
                threading.Thread(target=produce, args=(pid,))
                for pid in range(producers)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            producers_done.set()

        watcher = threading.Thread(target=watch_count)
        watcher.start()
        prod_runner = threading.Thread(target=run_producers)
        consumers = [threading.Thread(target=consume) for _ in range(2)]
        prod_runner.start()
        for t in consumers:
            t.start()
        for t in consumers:
            t.join(timeout=30)
            self.assertFalse(t.is_alive(), "消费者超时未结束")
        stop.set()
        watcher.join(timeout=5)
        prod_runner.join(timeout=5)

        self.assertEqual(rb.count(), 0)
        self.assertEqual(violations, [])
        self.assertEqual(len(consumed), total)
        self.assertEqual(len(consumed), len(set(consumed)))
        expected = {
            (pid, seq)
            for pid in range(producers)
            for seq in range(per_producer)
        }
        self.assertEqual(set(consumed), expected)


class TestMpmcWithOverwrite(unittest.TestCase):
    def test_no_duplicates_under_overwrite(self):
        # 覆盖语义下：消息可能因缓冲满被淘汰，但被交付的消息绝不重复，
        # count 始终在 [0, capacity]，交付的值都来自生产序列。
        rb = RingBuffer(16)
        producer_count = 4
        per_producer = 1000
        consumer_count = 4

        consumed = []
        consumed_lock = threading.Lock()
        violations = []
        producers_done = threading.Event()
        start = threading.Barrier(producer_count + consumer_count + 1)
        produced_total = producer_count * per_producer
        value_lock = threading.Lock()
        next_value = [0]

        def produce():
            start.wait()
            while True:
                with value_lock:
                    if next_value[0] >= produced_total:
                        return
                    value = next_value[0]
                    next_value[0] += 1
                rb.put(value)

        def consume():
            start.wait()
            while True:
                try:
                    item = rb.get()
                except Empty:
                    if producers_done.is_set():
                        return
                    continue
                with consumed_lock:
                    consumed.append(item)
                value = rb.count()
                if value < 0 or value > 16:
                    with consumed_lock:
                        violations.append(value)

        threads = [threading.Thread(target=produce)
                   for _ in range(producer_count)]
        threads += [threading.Thread(target=consume)
                    for _ in range(consumer_count)]
        for t in threads:
            t.start()
        start.wait()
        for t in threads[:producer_count]:
            t.join(timeout=30)
        producers_done.set()
        for t in threads[producer_count:]:
            t.join(timeout=30)
        for t in threads:
            self.assertFalse(t.is_alive(), "工作线程超时未结束")

        self.assertEqual(violations, [])
        self.assertEqual(len(consumed), len(set(consumed)))
        remaining = []
        try:
            while True:
                remaining.append(rb.get())
        except Empty:
            pass
        self.assertEqual(rb.count(), 0)
        all_delivered = consumed + remaining
        self.assertTrue(all(0 <= v < produced_total for v in all_delivered))
        self.assertEqual(len(all_delivered), len(set(all_delivered)))
        self.assertLessEqual(len(all_delivered), produced_total)


class TestConcurrentSnapshot(unittest.TestCase):
    def test_snapshot_never_corrupt(self):
        # snapshot 与 get/put 并发时不得抛异常，且任意快照都是
        # 已生产序列的合法滑动窗口：长度 == count()，元素单调递增、无重复。
        rb = RingBuffer(32)
        stop = threading.Event()
        bad_snapshots = []
        produced_count = 20000

        def producer():
            for i in range(produced_count):
                rb.put(i)

        def consumer():
            while not stop.is_set():
                try:
                    rb.get()
                except Empty:
                    pass

        def snapshotter():
            while not stop.is_set():
                snap = rb.snapshot()
                if len(snap) != rb.count() or snap != sorted(snap) \
                        or len(snap) != len(set(snap)):
                    bad_snapshots.append(list(snap))

        pt = threading.Thread(target=producer)
        cts = [threading.Thread(target=consumer) for _ in range(2)]
        st = threading.Thread(target=snapshotter)
        pt.start()
        for t in cts:
            t.start()
        st.start()
        pt.join(timeout=30)
        self.assertFalse(pt.is_alive())
        stop.set()
        for t in cts:
            t.join(timeout=5)
        st.join(timeout=5)
        self.assertEqual(bad_snapshots, [])


if __name__ == "__main__":
    unittest.main()
