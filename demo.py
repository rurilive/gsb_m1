"""SimpleTimer 现状演示。

第一段：注册若干任务，逐拍推进注入时钟，看到期任务被触发、取消之后不再
触发。
第二段：预留的分层时间轮演示位子（见文末注释）。
"""

from timewheel.wheel import SimpleTimer


def main():
    print("=== 朴素定时器 ===")
    t = SimpleTimer()
    t.add_at(2, "a")
    t.add_at(4, "b")
    t.add_at(4, "c")
    print("  注册 3 个任务，当前 size=%d，下一个到期时刻=%r" % (t.size, t.peek()))
    t.cancel("c")
    print("  取消 c 之后 size=%d" % t.size)
    print("  advance(2) 触发 -> %s" % t.advance(2))
    print("  advance(2) 触发 -> %s" % t.advance(2))
    print("  剩余 size=%d，时钟停在 %d" % (t.size, t.now))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
