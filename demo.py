"""regexlib 现状演示。

第一段：用当前的字面模式类跑几次整串与子串判断，看命中的位置结果。
第二段：预留的自动机改造演示位子（见文末注释）。
"""

from regexlib import LiteralPat, RegexError, literal_match, literal_search


def main():
    print("=== 字面匹配（现有能力） ===")
    print("  LiteralPat('abc').match('abc')      ->", LiteralPat("abc").match("abc"))
    print("  LiteralPat('abc').match('xabc')     ->", LiteralPat("abc").match("xabc"))
    print("  LiteralPat('abc').search('xxabcxx') ->", LiteralPat("abc").search("xxabcxx"))
    print("  LiteralPat('ab').finditer('ababab')->", LiteralPat("ab").finditer("ababab"))
    print("  literal_match('abc', 'abc')         ->", literal_match("abc", "abc"))
    print("  literal_search('abc', 'xxabcxx')    ->", literal_search("abc", "xxabcxx"))

    print("  说明：模式里眼下只有字面语义，整串相等才算整串命中，")
    print("        查找子串只做包含判断，星号、问号这些符号会直接报错。")
    try:
        LiteralPat("a*b")
    except RegexError as exc:
        print("  LiteralPat('a*b') 触发 RegexError ->", exc)

    # TODO: 第二段演示（实现后补）
    # 自动机改造完成后在这里补齐第二轮演示：准备若干固定模式与固定输入，
    # 先用非确定自动机跑一遍整串匹配与子串查找，再用确定化后的自动机跑同
    # 一批数据，逐项对比两侧结论是否一致；同时打印编译出来的状态数与转移
    # 数，展示同一模式在两种形态下的规模差异。


if __name__ == "__main__":
    main()
