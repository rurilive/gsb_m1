"""NaiveWildcard 现状演示。

第一段: 用几对文本与模式看递归回溯的判定结果与星号吃掉的长度。
第二段: 预留的填表或两指针演示位子 (见文末注释)。
"""

from wildcard import NaiveWildcard, star_lengths


def main():
    print("=== 朴素通配符匹配 (递归回溯) ===")
    cases = [
        ("", ""),
        ("abc", "a?c"),
        ("abc", "a*c"),
        ("aXXbXXc", "a*b*c"),
        ("", "***"),
        ("abcdef", "*"),
    ]
    for text, pattern in cases:
        w = NaiveWildcard(text, pattern)
        if w.matches():
            print(f"  text={text!r:12} pattern={pattern!r:8} -> match, lens={w.star_lengths()}")
        else:
            print(f"  text={text!r:12} pattern={pattern!r:8} -> no match")

    print(f"  star_lengths('a*b*c', 'axybzc') = {star_lengths('a*b*c', 'axybzc')}")
    print(f"  star_count of '*a**b*'          = {NaiveWildcard('', '*a**b*').star_count()}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
