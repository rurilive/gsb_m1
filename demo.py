"""sketchlib 现状演示。

第一段：跑通改造前的精确计数（live，可直接运行）。
第二段：概率计数素描就位后要补的演示位子（见文末注释）。
"""

from sketchlib import ExactCounter


def main():
    print("=== 精确计数 ===")
    counter = ExactCounter()
    for key in ["apple", "apple", "apple", "banana", "banana", "cherry"]:
        counter.add(key)
    print("  apple 计数:", counter.count("apple"))
    print("  banana 计数:", counter.count("banana"))
    print("  cherry 计数:", counter.count("cherry"))
    print("  缺失键计数:", counter.count("durian"))
    print("  不同键数:", counter.distinct())
    print("  总计数:", counter.total())
    print("  top(2):", counter.top(2))

    # TODO: 第二段演示（实现后补）

if __name__ == "__main__":
    main()
