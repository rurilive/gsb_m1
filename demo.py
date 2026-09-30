"""FlatPrefixSet 现状演示。

第一段: 插入若干单词, 看线性扫描下的前缀判定、前缀计数、完整单词判定、
按字典序输出、最长公共前缀与通配符匹配。
第二段: 预留的字典树演示位子 (见文末注释)。
"""

from triex2.trie import FlatPrefixSet


def main():
    print("=== 朴素前缀集合 ===")
    s = FlatPrefixSet()
    for w in ("app", "apple", "app", "apricot", "bat", "banana", "band"):
        s.insert(w)

    print(f"  len                 = {len(s)}")
    print(f"  all_words           = {s.all_words()}")
    print(f"  has_prefix(ap)      = {s.has_prefix('ap')}")
    print(f"  count_prefix(ap)    = {s.count_prefix('ap')}")
    print(f"  contains(apple)     = {s.contains('apple')}")
    print(f"  words_with_prefix(b)= {s.words_with_prefix('b')}")
    print(f"  longest_common      = {s.longest_common_prefix()}")
    print(f"  match(app.e)        = {s.match_pattern('app.e')}")

    s.remove("app")
    print(f"  after remove(app), count_prefix(app) = {s.count_prefix('app')}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
