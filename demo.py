"""pushbuf 现状演示。

第一段：无界缓冲的入队与出队、先进先出次序、空缓冲上的取值。
第二段：预留的背压演示位子（见文末注释）。
"""

from pushbuf import UnboundedBuffer


def main():
    print("=== 无界缓冲入队与出队 ===")
    buf = UnboundedBuffer()
    buf.put("a")
    buf.put("b")
    buf.put("c")
    print("  当前深度:", len(buf))
    print("  先出:", buf.get())
    print("  再出:", buf.get())
    print("  当前深度:", len(buf))
    print("  先看一眼:", buf.peek())

    # TODO(背压改造): 有界容量、可配策略（阻塞等待、立即拒绝、丢弃最旧）、
    # 高低水位与背压信号、容量释放后按先到先服务唤醒等待写者、深度与容量与
    # 被拒次数与被丢弃次数与高水位触发次数的计量、容量为零与水位配置越界的
    # fail fast 就位后，在这里补一遍演示：把队列填到满，打印深度、容量与背压
    # 信号是否触发；对同一侧再写一次，打印被拒次数或丢弃端；取走若干个释放
    # 名额，打印被唤醒的写者顺序与释放前后的高水位触发次数。


if __name__ == "__main__":
    main()
