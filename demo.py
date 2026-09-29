"""Small demonstration of the ropetex text buffer.

Run with: python3 demo.py
"""

from ropetex import FlatText


def baseline_demo():
    t = FlatText("hello world")
    print("initial:", t.toString())

    t.insert(5, ",")
    print("after insert:", t.toString())

    t.delete(0, 1)
    print("after delete(0, 1):", t.toString())

    chars = [t.charAt(i) for i in range(len(t))]
    print("charAt each:", "".join(chars))


# TODO(绳结构改造): 在第二段演示里补一轮插入删除与拼接,
# 展示绳结构在跨块边界插入删除以及两段文本拼接后各自独立修改上的行为。


if __name__ == "__main__":
    baseline_demo()
