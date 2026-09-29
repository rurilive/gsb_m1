"""Small demonstration of the persistx sequence library.

Run with: python3 demo.py
"""

from persistx import MutList


def baseline_demo():
    m = MutList([1, 2, 3])
    print("initial:", m.snapshot())

    m.push(4).push(5)
    print("after push:", m.snapshot())

    m.set(0, 100)
    print("after set(0, 100):", m.snapshot())

    tail = m.pop()
    print("popped:", tail, "now:", m.snapshot())

    snap = m.snapshot()
    m.push(6)
    print("old snapshot stays:", snap, "live list:", m.snapshot())


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    baseline_demo()
