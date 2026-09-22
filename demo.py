"""lexbend 现状演示。

第一段：一小段公式过一遍全文扫描，看 token 与行列。
第二段：模拟逐字输入，每敲一键整段重扫一次，看次数和成本涨得有多快。
第三段：把稿子铺到十万 token 量级，量一次全量重扫要多久。
（增量重扫的位子在文末留好了。）
"""

import time

from lexbend import COMMENT, EOF, ERROR, TextBuffer, scan

KIND_LABEL = {
    "IDENT": "名字",
    "NUMBER": "数字",
    "STRING": "字符串",
    "OP": "运算符",
    "COMMENT": "注释",
    "ERROR": "错误",
    "EOF": "文末",
}

SAMPLE = (
    "# 面积换算\n"
    'formula = width * height + "px"\n'
    "if formula <= 120 { scale -> apply }\n"
)


def show_tokens(text):
    """打印一段文本的 token 表，带区间与行列。"""
    for token in scan(text):
        shown = token.text if token.kind != EOF else "<文末>"
        print("  %-4s %-8s [%2d, %2d)  行%d 列%d  %s" % (
            KIND_LABEL[token.kind], token.kind, token.start, token.end,
            token.line, token.col, shown))
    kinds = {}
    for token in scan(text):
        kinds[token.kind] = kinds.get(token.kind, 0) + 1
    print("  小结：%s" % ", ".join(
        "%s %d" % (KIND_LABEL[k], v) for k, v in sorted(kinds.items())))


def type_along(text):
    """逐字敲进缓冲，每敲一键整段重扫，返回 (击键数, 重扫秒数)。"""
    buf = TextBuffer()
    spent = 0.0
    for offset, ch in enumerate(text):
        buf.insert(offset, ch)
        started = time.perf_counter()
        buf.scan()
        spent += time.perf_counter() - started
    return buf.scan_count, spent


def build_script(lines):
    """铺一份够大的表达式稿子：每行一条赋值加一句备注。"""
    return "".join(
        'total_%d = price_%d * (base + %d.5) # 第 %d 行\n' % (i, i, i, i)
        for i in range(lines))


def main():
    print("=== 一小段公式 ===")
    show_tokens(SAMPLE)

    print("=== 打字就整段重扫 ===")
    count, spent = type_along(SAMPLE)
    print("  敲了 %d 个字符，整段重扫 %d 次，共 %.1f 毫秒" % (count, count, spent * 1000))

    print("=== 稿子铺大之后 ===")
    big = build_script(4000)
    buf = TextBuffer(big)
    started = time.perf_counter()
    tokens = buf.scan()
    one_pass = time.perf_counter() - started
    print("  稿子 %d 字符，%d 个 token" % (len(big), len(tokens)))
    print("  一次全量扫描 %.1f 毫秒" % (one_pass * 1000))

    strokes = 10
    started = time.perf_counter()
    for i in range(strokes):
        spot = len(big) // 2 + i
        buf.insert(spot, "x")
        buf.scan()
    typed = time.perf_counter() - started
    print("  在稿子中间敲 %d 下：每下重扫一遍全篇，共 %.1f 毫秒（平均 %.1f 毫秒/下）"
          % (strokes, typed * 1000, typed * 1000 / strokes))
    print("  二十万 token 的稿子敲五千下，照这个路子要 %.0f 秒" % (
        typed / strokes * 5000 * 5))
    print("  （TextBuffer 累计整段重扫 %d 次）" % buf.scan_count)

    noisy = '# 结尾注释还开着 "没关上的串\nlet x = @\n'
    print("=== 烂边角：错误 token 长什么样 ===")
    for token in scan(noisy):
        if token.kind in (ERROR, COMMENT):
            print("  %-4s [%d, %d) 行%d 列%d  %r" % (
                KIND_LABEL[token.kind], token.start, token.end,
                token.line, token.col, token.text))

    # TODO(增量重扫): IncrementalLexer 落地后，在这里补一段：
    # 同一份 big 稿子喂给它，先把 tokens() 和 scan(big) 的逐 token 对拍，
    # 再连敲五千下，把总耗时和上面整段重扫的路子比一比。


if __name__ == "__main__":
    main()
