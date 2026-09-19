"""边框样式表：四套样式各是一条数据，不再有四段 if/elif 复制粘贴。

每套样式只声明两类素材：
  - 纵向字符 vertical；
  - 一组角点/连接点字形（上/中/下三行，每行 左/交点/右）和横线字符。
横线规则全部由同一个 rule() 生成，新增样式只需补一行样式数据。
markdown 没有横线规则（None），其表头分隔线单独按历史写法生成。
"""


class BorderStyle(object):
    __slots__ = (
        "name",
        "vertical",
        "horizontal",
        "top_glyphs",
        "mid_glyphs",
        "bottom_glyphs",
    )

    def __init__(self, name, vertical, horizontal, top_glyphs,
                 mid_glyphs, bottom_glyphs):
        self.name = name
        self.vertical = vertical
        self.horizontal = horizontal
        self.top_glyphs = top_glyphs
        self.mid_glyphs = mid_glyphs
        self.bottom_glyphs = bottom_glyphs

    def rule(self, widths, glyphs):
        """按一组 (左角, 交点, 右角) 字形生成一条横线规则。"""
        left, join, right = glyphs
        segment = self.horizontal
        return (
            left
            + join.join([segment * (w + 2) for w in widths])
            + right
        )

    def top_rule(self, widths):
        if self.top_glyphs is None:
            return None
        return self.rule(widths, self.top_glyphs)

    def mid_rule(self, widths):
        if self.mid_glyphs is None:
            return None
        return self.rule(widths, self.mid_glyphs)

    def bottom_rule(self, widths):
        if self.bottom_glyphs is None:
            return None
        return self.rule(widths, self.bottom_glyphs)

    def header_separator(self, widths):
        """表头与数据之间的分隔行（每个样式一条）。"""
        if self.name == "markdown":
            sep = "|"
            for w in widths:
                sep = sep + " " + "-" * w + " |"
            return sep
        return self.mid_rule(widths)


_PLUS = ("+", "+", "+")

STYLES = {
    "ascii": BorderStyle(
        "ascii", "|", "-", _PLUS, _PLUS, _PLUS,
    ),
    "light": BorderStyle(
        "light", "│", "─",
        ("┌", "┬", "┐"),
        ("├", "┼", "┤"),
        ("└", "┴", "┘"),
    ),
    "heavy": BorderStyle(
        "heavy", "┃", "━",
        ("┏", "┳", "┓"),
        ("┣", "╋", "┫"),
        ("┗", "┻", "┛"),
    ),
    "markdown": BorderStyle(
        "markdown", "|", None, None, None, None,
    ),
}


def get_style(name):
    """按名查样式表；未知样式沿用历史报错（发生在 render 时）。"""
    try:
        return STYLES[name]
    except KeyError:
        raise ValueError("unknown style: %r" % (name,))
