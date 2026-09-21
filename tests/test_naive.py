"""TaskQueue 与排序列表参考实现 SortedListQueue 的小规模对拍。"""

import random
import unittest

from taskheap import SortedListQueue, TaskQueue


def run_script(queue, script):
    """把一份 push/pop 脚本跑一遍，返回依次弹出的任务号。"""
    served = []
    for op in script:
        if op[0] == "push":
            queue.push(op[1], op[2])
        else:
            served.append(queue.pop())
    return served


def random_script(seed, count):
    rnd = random.Random(seed)
    script = []
    for index in range(count):
        if script and rnd.random() < 0.4:
            script.append(("pop",))
        else:
            script.append(("push", "task-%03d" % index, rnd.randrange(1, 1000)))
    return script


class TestAgainstSortedList(unittest.TestCase):
    def test_distinct_priorities_agree(self):
        script = random_script(seed=41, count=300)
        self.assertEqual(run_script(TaskQueue(), script),
                         run_script(SortedListQueue(), script))

    def test_queues_drain_identically(self):
        script = random_script(seed=42, count=200)
        fast, slow = TaskQueue(), SortedListQueue()
        run_script(fast, script)
        run_script(slow, script)
        self.assertEqual(fast.pop_batch(400), slow.pop_batch(400))
