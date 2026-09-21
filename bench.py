"""taskheap 吞吐对照：同一段混合操作分别打给 TaskQueue 和排序列表参考实现。

默认队列里常驻三千条任务，再跑十万次 push、调优先级、弹出、回滚的混合操作，
打印两边各自耗时和倍数。倍数就是队列相对朴素排序列表的吞吐优势，默认规模下
掉到十倍以内说明这份实现已经不值当了。

用法：python3 bench.py [队列规模] [操作条数]
"""

import random
import sys
import time

from taskheap import SortedListQueue, TaskQueue

PUSH_RATIO = 0.30
UPDATE_RATIO = 0.25


def run(queue, live_n, ops_n, seed=5):
    """跑一段混合操作，返回耗时（秒）和结束时的观察值。"""
    rnd = random.Random(seed)
    live, where = [], {}

    def add(task_id):
        where[task_id] = len(live)
        live.append(task_id)

    def remove(task_id):
        if task_id not in where:
            return False
        index = where.pop(task_id)
        last = live.pop()
        if index < len(live):
            live[index] = last
            where[last] = index
        return True

    counter = 0
    for _ in range(live_n):
        task_id = "t%08d" % counter
        counter += 1
        queue.push(task_id, rnd.randrange(10000))
        add(task_id)

    started = time.perf_counter()
    for _ in range(ops_n):
        roll = rnd.random()
        if roll < PUSH_RATIO:
            task_id = "t%08d" % counter
            counter += 1
            queue.push(task_id, rnd.randrange(10000))
            add(task_id)
        elif roll < PUSH_RATIO + UPDATE_RATIO and live:
            try:
                queue.update_priority(live[rnd.randrange(len(live))],
                                      rnd.randrange(10000))
            except KeyError:
                pass
        else:
            task_id = queue.pop()
            if task_id is None or not remove(task_id):
                # 队列把同一个任务弹了第二遍时驱动侧当没看见
                continue
            try:
                if rnd.random() < 0.7:
                    queue.done(task_id)
                else:
                    queue.release(task_id)
                    add(task_id)
            except KeyError:
                pass
    elapsed = time.perf_counter() - started
    return elapsed, queue.size(), queue.capacity()


def main(live_n=3000, ops_n=100000):
    print("队列常驻 %d 条，混合操作 %d 次" % (live_n, ops_n))
    fast, size, capacity = run(TaskQueue(), live_n, ops_n)
    print("TaskQueue       %8.3fs  剩 %d 条，capacity %d" % (fast, size, capacity))
    slow, size, capacity = run(SortedListQueue(), live_n, ops_n)
    print("SortedListQueue %8.3fs  剩 %d 条，capacity %d" % (slow, size, capacity))
    print("倍数 %.1fx，规模越小倍数越缩，默认规模下的底线是十倍" % (slow / fast))


if __name__ == "__main__":
    main(*[int(value) for value in sys.argv[1:3]])
