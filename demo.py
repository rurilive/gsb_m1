"""taskheap 现状演示：在线调优先级、执行失败回滚、长跑容量、跟参考实现对拍。

每个场景先把现场操作跑一遍再打印实际结果，带“期望”的那行是修好之后该有
的样子，跑在现在的代码上多半对不上。
"""

import random

from taskheap import SortedListQueue, TaskQueue


def scenario_update_priority():
    print("=== 场景一：调高优先级之后，任务被弹了两次 ===")
    queue = TaskQueue()
    queue.push("render", 9)
    queue.push("index", 5)
    queue.push("report", 7)
    queue.update_priority("render", 1)
    print("  调整后 pending ->", queue.pending())
    print("  连续弹出 ->", queue.pop_batch(4))
    print("  期望：['render', 'index', 'report']，render 只出现一次")

    print("=== 场景二：调低优先级，旧优先级还在顶着 ===")
    queue = TaskQueue()
    queue.push("report", 3)
    queue.push("index", 4)
    queue.update_priority("report", 8)
    print("  pending ->", queue.pending())
    print("  期望：['index', 'report']，report 让位给 index")


def scenario_same_priority():
    print("=== 场景三：同优先级的任务不按提交顺序走 ===")
    queue = TaskQueue()
    for task_id in ("gamma", "delta", "beta", "alpha"):
        queue.push(task_id, 5)
    print("  提交顺序 gamma, delta, beta, alpha")
    print("  弹出 ->", queue.pop_batch(4))
    print("  期望：['gamma', 'delta', 'beta', 'alpha']")


def scenario_release_rollback():
    print("=== 场景四：执行失败放回队列，位置就不对了 ===")
    queue = TaskQueue()
    for task_id, prio in (("a", 1), ("b", 2), ("c", 3), ("d", 4)):
        queue.push(task_id, prio)
    print("  第一批弹出 ->", queue.pop_batch(2))
    queue.release("a")
    print("  a 放回后 pending ->", queue.pending())
    print("  后续弹出 ->", queue.pop_batch(3))
    print("  期望：放回后 a 回到队首，后续弹出 ['a', 'c', 'd']")


def scenario_capacity_growth():
    print("=== 场景五：长跑之后容量只涨不落 ===")
    queue = TaskQueue()
    for index in range(20000):
        queue.push("job-%05d" % index, index % 97)
        if index % 2 == 0:
            queue.update_priority("job-%05d" % index, 200 + index % 11)
    repeats = 0
    while queue.size() > 50:
        for task_id in queue.pop_batch(queue.size() - 50):
            try:
                queue.done(task_id)
            except KeyError:
                repeats += 1
    print("  队列里剩 %d 条，capacity -> %d，排空过程里重复弹出 %d 次"
          % (queue.size(), queue.capacity(), repeats))
    print("  期望：capacity 跟元素数同量级，也不该有重复弹出")


def scenario_against_reference():
    print("=== 场景六：跟排序列表参考实现对拍 ===")
    rnd = random.Random(20260921)
    fast, slow = TaskQueue(), SortedListQueue()
    running, counter, pops, step = [], 0, 0, 0
    while step < 400:
        step += 1
        queued = slow.pending()
        roll = rnd.random()
        try:
            if roll < 0.45 or not queued:
                counter += 1
                task_id, prio = "t%04d" % counter, rnd.randrange(1, 8)
                fast.push(task_id, prio)
                slow.push(task_id, prio)
            elif roll < 0.6:
                task_id, prio = rnd.choice(queued), rnd.randrange(1, 8)
                fast.update_priority(task_id, prio)
                slow.update_priority(task_id, prio)
            elif roll < 0.85 or not running:
                pops += 1
                got, want = fast.pop(), slow.pop()
                if got != want:
                    print("  第 %d 次弹出就对不上：实际 %r，参考实现 %r"
                          % (pops, got, want))
                    break
                if got is not None:
                    running.append(got)
            elif roll < 0.95:
                task_id = running.pop(rnd.randrange(len(running)))
                fast.done(task_id)
                slow.done(task_id)
            else:
                task_id = running.pop(rnd.randrange(len(running)))
                fast.release(task_id)
                slow.release(task_id)
        except KeyError as exc:
            print("  第 %d 步 %r 报 KeyError" % (step, exc))
            break
    else:
        print("  两种实现逐步一致")
    print("  期望：整段脚本跑下来两种实现逐步一致")


def main():
    scenario_update_priority()
    print()
    scenario_same_priority()
    print()
    scenario_release_rollback()
    print()
    scenario_capacity_growth()
    print()
    scenario_against_reference()


if __name__ == "__main__":
    main()
