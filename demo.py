"""autolab 现状演示。

第一段：用最朴素的自动机模拟器跑几次判断，看一个含偶数个 a 的自动机
对若干输入串接受与否。
第二段：预留的自动机运算与最小化改造演示位子（见文末注释）。
"""

from autolab import NaiveDFA


def main():
    print("=== 朴素 DFA 模拟（现有能力） ===")
    dfa = NaiveDFA(
        transitions={
            ("even", "a"): "odd",
            ("even", "b"): "even",
            ("odd", "a"): "even",
            ("odd", "b"): "odd",
        },
        start="even",
        accepts={"even"},
    )
    for text in ["", "a", "ab", "aa", "abab"]:
        print("  accepts_str(%r) ->" % text, dfa.accepts_str(text))
    print("  说明：现在只会逐字符走状态表判断接受与否，")
    print("        没有可达性清理、没有等价类、没有最小化、没有补集。")

    # TODO(自动机运算与最小化改造): 运算与最小化就位后，在这里补一段演示：
    # 先对一个小 DFA 做可达性清理，打印清理前后的状态数并确认接受语言不变；
    # 再演示补集与并、交乘积构造，用若干有限串验证结果语义正确；接着做
    # 等价类划分得到最小 DFA，打印最小化前后的状态数；最后把最小 DFA 转成
    # 正则表达式，或从简单正则构造 DFA，做一次往返并确认接受语言一致。


if __name__ == "__main__":
    main()
