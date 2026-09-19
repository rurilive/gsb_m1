"""演示：单线程走一遍写入/导出/读取，观察计数与内容。"""
from ringbuf import Empty, RingBuffer


def main():
    rb = RingBuffer(3)
    for ch in "abcde":
        rb.put(ch)
    print(f"写入 a b c d e 后 count = {rb.count()}（容量 3）")
    print(f"snapshot = {rb.snapshot()}")
    drained = []
    try:
        while True:
            drained.append(rb.get())
    except Empty:
        pass
    print(f"依次取出: {' '.join(drained)}")
    print("演示结束")


if __name__ == "__main__":
    main()
