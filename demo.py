"""rexflow 现状演示：整串匹配、朴素搜索、错误定位与代价。

跑法：python3 demo.py
"""

import time

from rexflow import Pattern, PatternError, compile


def show_fullmatch():
    pat = compile("ab*c")
    print("=== 整串匹配 ===")
    for text in ("abc", "abbbc", "ac", "abx"):
        print("  fullmatch(%r) -> %s" % (text, pat.fullmatch(text)))


def show_search():
    print("=== 搜索 ===")
    pat = compile("ab*c")
    for text in ("xxabbc yy", "这里没有匹配"):
        got = pat.search(text)
        print("  search(%r) -> %s" % (text, got.span() if got else None))
    got = compile("a*").search("baa")
    print("  search('a*', 'baa') -> %s（最左的空匹配）" % (got.span(),))


def show_error():
    print("=== 语法错误定位 ===")
    try:
        compile("ab*(c")
    except PatternError as exc:
        print("  " + str(exc).replace("\n", "\n  "))


def show_cost():
    print("=== 朴素搜索的代价 ===")
    for size in (40, 80, 160):
        text = "a" * size
        pat = Pattern("a*a*b")
        start = time.perf_counter()
        got = pat.search(text)
        cost = (time.perf_counter() - start) * 1000.0
        print("  %d 个 a，模式 a*a*b -> %s，耗时 %.1f ms"
              % (size, got, cost))


# TODO(NFA 执行): rexflow/engine.py 落地后在这里补一段演示：
# 1) 新语法（交替、分组、字符类、锚点）在长文本上搜索，打印区间与各分组
# 2) 嵌套量词对长串，展示毫秒级出结论，对照上面 show_cost 的朴素耗时
# 3) 小输入上跟老回溯实现（rexflow.matcher）对拍，打印两边区间一致


def main():
    show_fullmatch()
    show_search()
    show_error()
    show_cost()


if __name__ == "__main__":
    main()
