"""taskq 现状演示。

第一段：朴素先进先出队列的入队、出队与窥视。
第二段：预留的优先级、延迟与重试演示位子（见文末注释）。
"""

from taskq.queue import FifoQueue


def main():
    print("=== 先进先出队列 ===")
    q = FifoQueue()
    for name in ("alpha", "beta", "gamma"):
        q.push(name)
    print("  入队后队列长度:", len(q))
    print("  peek 看一眼队首:", q.peek())
    print("  依次出队:", [q.pop(), q.pop(), q.pop()])
    print("  空队列出队:", q.pop())

    # TODO(优先级、延迟与重试): 优先级调度器实现后，在这里加一段演示：
    # 用注入的假时钟入队一个带延迟的任务，观察不到点时取不到、推时钟到点后可见；
    # 再演示一次取走任务附上租约、不确认则租约到期重新可见并被再次取走，
    # 重试次数耗尽后任务落进死信队列，最后查看死信队列里的内容。


if __name__ == "__main__":
    main()