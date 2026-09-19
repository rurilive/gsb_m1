"""边框样式表：一套字符定义一种样式。加样式只动这里，不用碰 render。

每种样式：
  top/mid/bot：(左端, 横线, 交叉, 右端)，None 表示不画这一行
  v：竖线字符
  header_sep：表头下方的分隔，"border" 画 mid 边框，"markdown" 画 | --- | 行
"""

STYLES = {
    "ascii": {
        "top": ("+", "-", "+", "+"),
        "mid": ("+", "-", "+", "+"),
        "bot": ("+", "-", "+", "+"),
        "v": "|",
        "header_sep": "border",
    },
    "light": {
        "top": ("┌", "─", "┬", "┐"),
        "mid": ("├", "─", "┼", "┤"),
        "bot": ("└", "─", "┴", "┘"),
        "v": "│",
        "header_sep": "border",
    },
    "heavy": {
        "top": ("┏", "━", "┳", "┓"),
        "mid": ("┣", "━", "╋", "┫"),
        "bot": ("┗", "━", "┻", "┛"),
        "v": "┃",
        "header_sep": "border",
    },
    "markdown": {
        "top": None,
        "mid": None,
        "bot": None,
        "v": "|",
        "header_sep": "markdown",
    },
}


def get_style(name):
    """按名字取样式，未知样式在 render 时抛 ValueError（历史行为）。"""
    try:
        return STYLES[name]
    except KeyError:
        raise ValueError("unknown style: %r" % (name,))


def border_line(chars, widths):
    """拼一条横向边框线：左端 + 各列横线（宽+2）用交叉符连接 + 右端。"""
    left, fill, joint, right = chars
    return left + joint.join(fill * (w + 2) for w in widths) + right
