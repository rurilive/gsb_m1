"""rex 现状演示。

第一段：看现有字面量匹配与 findall。
第二段：预留的迭代演示位子（见文末注释）。
"""

from rex import findall, match, search


def main():
    print("=== 字面量匹配（现有能力） ===")
    print("  match('abc', 'abc')      ->", match("abc", "abc"))
    print("  match('abc', 'xxabcxx')  ->", match("abc", "xxabcxx"))
    print("  search('abc', 'abc')     ->", search("abc", "abc"))
    print("  findall('abc', 'abc')    ->", findall("abc", "abc"))
    print("  findall('abc', 'xxabcxx')->", findall("abc", "xxabcxx"))
    print("  说明：模式里现在只有字面量语义，整段相等才算命中。")

    # TODO(元字符与分组改造): NFA 引擎、量词与分组就位后，在这里补一段演示：
    # 用 r'a.c' 演示点号匹配任意字符，用 r'ab*c' 演示星号的零次或多次，
    # 用 r'[a-z]+' 演示字符类与加法，用 r'(\d+)-(\d+)' 演示分组与捕获，
    # 打印每个捕获组的内容与位置；再用 search 在一段长文本里找子串命中，
    # 用 findall 列出全部命中，并对非法模式捕获编译期报错以确认 fail fast。


if __name__ == "__main__":
    main()
