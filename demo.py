"""regexlab 现状演示。

第一段：用最朴素的字面量相等匹配器跑几次判断，看命中与未命中的
跨度结果。
第二段：预留的正则引擎改造演示位子（见文末注释）。
"""

from regexlab import LiteralMatch, match


def main():
    print("=== 字面量相等匹配（现有能力） ===")
    print("  LiteralMatch('abc').test('abc')   ->", LiteralMatch("abc").test("abc"))
    print("  LiteralMatch('abc').test('abx')   ->", LiteralMatch("abc").test("abx"))
    print("  LiteralMatch('abc').span('abc')   ->", LiteralMatch("abc").span("abc"))
    print("  LiteralMatch('abc').span('xxabc') ->", LiteralMatch("abc").span("xxabc"))
    print("  match('abc', 'abc')               ->", match("abc", "abc"))
    print("  match('abc', 'xxabcxx')           ->", match("abc", "xxabcxx"))
    print("  说明：模式里现在只有字面量语义，整段相等才算命中，")
    print("        点号、星号、方括号等符号全被当成普通字符。")

    # TODO(正则引擎改造): 解析器、NFA 与状态集合模拟就位后，在这里补一段演示：
    # 用 a.c 演示点号匹配任意单字符，用 ab*c 与 ab+c 演示星号与加号的贪婪
    # 口径，用 ab*?c 演示懒惰口径下的最短匹配；用 [a-z]+ 演示字符类与区间；
    # 用 ^...$ 演示行首行尾锚点，并分别调用整串匹配入口与查找子串入口，打印
    # 首个匹配的起点与终点；用 (\d+)-(\d+) 演示分组捕获，打印每个捕获组的
    # 文本与区间；再用一个回溯引用模式演示引用前面分组已匹配到的内容；最后
    # 拿一个非法模式调用一次，捕获 RegexError 以确认非法正则在编译期就报错。


if __name__ == "__main__":
    main()
