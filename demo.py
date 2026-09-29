"""seekr 现状演示。

第一段：搭一撮小文档，用朴素子串扫描查一个词、看命中文档与出现次数；
第二段：预留的分词倒排、布尔与短语检索、评分排序演示位子（见文末注释）。
"""

from seekr.scan import Corpus


def main():
    print("=== 朴素子串扫描 ===")
    c = Corpus()
    c.add("a", "the quick brown fox")
    c.add("b", "quick quick brown bear")
    c.add("c", "lazy dogs sleep")
    print("  文档 %s" % (c.doc_ids(),))
    print("  search brown -> %s" % c.search("brown"))
    print("  search quick -> %s" % c.search("quick"))
    print("  count quick -> %d" % c.count("quick"))
    print("  search zebra -> %s" % c.search("zebra"))
    c.remove("b")
    print("  删掉 b 后 search quick -> %s" % c.search("quick"))

    # TODO(倒排与检索): 在 seekr 里补出分词建倒排（词到文档及位置）、布尔 and/or/not
    # 短路组合、短语相邻匹配、按词频与文档长度评分降序、命中词位置与增删后倒排
    # 一致性之后，在这里加一段演示：先 add 几篇文档建好倒排，对同一组词项分别用
    # 布尔组合与朴素集合运算求命中文档，打印两边结果确认一致；再用 phrase 查一个
    # 相邻词组，打印命中的文档与命中的位置；最后对单个词项跑评分检索，打印按分
    # 降序的文档名单与各自得分，再删掉一篇文档，打印倒排里该词项对应的文档集合，
    # 确认被删的文档已经没有残留。


if __name__ == "__main__":
    main()