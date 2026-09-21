"""texttbl.render：把二维数据渲染成带边框的文本表格。

监控后台和 CLI 工具在用。2019 年写的，输出被 tests/ 逐字节锁着
（有几个后台直接 diff 表格输出做告警），别动格式。

渲染管线分三步，各步互不纠缠：
1. 切块：原始文本 -> Cell（已换行的行）；同列的表头/数据格归到 Column
2. 度量：Column -> 列宽（纯函数 compute_column_widths）
3. 拼装：按 STYLES 样式表把已度量的表格拼成字符串
"""

from functools import lru_cache


@lru_cache(maxsize=None)
def _text_width(s):
    """显示宽度（纯函数，历史口径：按 len() 算，中文也按 1 个宽）。

    结果由 lru_cache 收口缓存，不再暴露谁都能写的全局 dict；
    需要时用 ``_text_width.cache_clear()`` 清空。
    """
    return len(s)


def _wrap_cell(text, wrap):
    """把单元格文本切成若干行（纯函数）。wrap<=0 不换行。

    词间换行（连续空白当一个分隔），超长词硬切。历史口径，别改。
    """
    if wrap is None or wrap <= 0:
        return [text]
    tokens = text.split()
    if len(tokens) == 0:
        return [""]
    lines = []
    cur = ""
    for word in tokens:
        while _text_width(word) > wrap:
            if cur != "":
                lines.append(cur)
                cur = ""
            lines.append(word[0:wrap])
            word = word[wrap:]
        if cur == "":
            cur = word
        elif _text_width(cur) + 1 + _text_width(word) <= wrap:
            cur = cur + " " + word
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


class Cell(object):
    """单元格数据：原文、换行后的行（lines）和行高（height）。"""

    def __init__(self, text, wrap):
        self.text = text
        self.lines = _wrap_cell(text, wrap)
        self.height = len(self.lines)

    def line_at(self, line_index):
        """该物理行上的文本；行已占满时取空串。"""
        if line_index < self.height:
            return self.lines[line_index]
        return ""


class Column(object):
    """列数据：表头 Cell、该列数据 Cell 及算出的列宽。"""

    def __init__(self, header, cells):
        self.header = header
        self.cells = cells
        self.width = 0

    def iter_cells(self):
        """参与列宽/渲染的全部格子，表头在第一个。"""
        yield self.header
        for cell in self.cells:
            yield cell


def compute_column_widths(columns):
    """列宽纯函数：全表（含表头）按显示宽逐行取最大，返回宽度列表。"""
    widths = []
    for column in columns:
        width = 0
        for cell in column.iter_cells():
            for line in cell.lines:
                line_width = _text_width(line)
                if line_width > width:
                    width = line_width
        widths.append(width)
    return widths


class BorderStyle(object):
    """边框样式表：一套样式用到的全部字符和横线拼法。

    横线 = 左端 + 每列一段 dash*(宽+2)（中段连接符串起）+ 右端；
    没有上下框线的样式（markdown）把各元组留 None。
    """

    def __init__(self, vertical, dash, top, mid, bottom, header_separator=None):
        self.vertical = vertical
        self.dash = dash
        self.top = top
        self.mid = mid
        self.bottom = bottom
        self.header_separator = header_separator

    def rule(self, kind, widths):
        left, join, right = getattr(self, kind)
        return left + join.join([self.dash * (w + 2) for w in widths]) + right

    def separator(self, widths):
        """表头下的分隔行：markdown 用历史写法，其余走中段横线。"""
        if self.header_separator is not None:
            return self.header_separator(widths)
        return self.rule("mid", widths)


def _markdown_separator(widths):
    sep = "|"
    for width in widths:
        sep = sep + " " + "-" * width + " |"
    return sep


STYLES = {
    "ascii": BorderStyle(
        vertical="|",
        dash="-",
        top=("+", "+", "+"),
        mid=("+", "+", "+"),
        bottom=("+", "+", "+"),
    ),
    "light": BorderStyle(
        vertical="│",
        dash="─",
        top=("┌", "┬", "┐"),
        mid=("├", "┼", "┤"),
        bottom=("└", "┴", "┘"),
    ),
    "heavy": BorderStyle(
        vertical="┃",
        dash="━",
        top=("┏", "┳", "┓"),
        mid=("┣", "╋", "┫"),
        bottom=("┗", "┻", "┛"),
    ),
    "markdown": BorderStyle(
        vertical="|",
        dash="-",
        top=None,
        mid=None,
        bottom=None,
        header_separator=_markdown_separator,
    ),
}


def _build_columns(headers, rows, wrap):
    """第一步 切块：原始文本 -> Cell -> Column（每列含表头和数据格）。"""
    columns = []
    for i in range(len(headers)):
        cells = []
        for row in rows:
            if i < len(row):
                cells.append(Cell(row[i], wrap))
            else:
                cells.append(Cell("", wrap))
        columns.append(Column(Cell(headers[i], wrap), cells))
    return columns


def _pad_line(text, width):
    """一格的物理行：左右各一个空格，右侧补到列宽（左对齐）。"""
    return " " + text + " " * (width - _text_width(text)) + " "


def _content_line(cells, line_index, widths, vertical):
    """一行物理行：同行各格同一高度上的文本用竖线拼起。"""
    parts = []
    for i, cell in enumerate(cells):
        parts.append(_pad_line(cell.line_at(line_index), widths[i]))
    return vertical + vertical.join(parts) + vertical


def _assemble(border, columns, widths, row_count):
    """第三步 拼装：已切块、已度量的表格 -> 输出行列表。"""
    vertical = border.vertical
    headers = [column.header for column in columns]
    data_rows = [[column.cells[r] for column in columns] for r in range(row_count)]

    lines = []
    if border.top is not None:
        lines.append(border.rule("top", widths))

    header_height = max([1] + [cell.height for cell in headers])
    for line_index in range(header_height):
        lines.append(_content_line(headers, line_index, widths, vertical))

    # markdown 分隔行恒画；其余样式空表不画数据分隔线
    if border.header_separator is not None:
        lines.append(border.separator(widths))
    elif data_rows:
        lines.append(border.rule("mid", widths))

    for row in data_rows:
        row_height = max([1] + [cell.height for cell in row])
        for line_index in range(row_height):
            lines.append(_content_line(row, line_index, widths, vertical))

    if border.bottom is not None:
        lines.append(border.rule("bottom", widths))
    return lines


class Table(object):
    """文本表格。用法：Table(["列A", "列B"], style="ascii", wrap=0)。

    add_row 传的格子数可以比列少（缺的当空串），比列多直接报错。
    render() 返回不带尾换行的整表文本。
    """

    def __init__(self, headers, style="ascii", wrap=0):
        self._headers = [str(h) for h in headers]
        self._rows = []
        self._style = style
        self._wrap = wrap

    def add_row(self, *cells):
        if len(cells) > len(self._headers):
            raise ValueError(
                "too many cells: got %d, want %d" % (len(cells), len(self._headers))
            )
        self._rows.append([str(c) for c in cells])
        return self

    def render(self):
        try:
            border = STYLES[self._style]
        except (KeyError, TypeError):
            raise ValueError("unknown style: %r" % (self._style,))

        # 第一步 切块：原始文本 -> Cell -> Column（内容/行高是数据）
        columns = _build_columns(self._headers, self._rows, self._wrap)
        # 第二步 度量：列宽纯函数
        widths = compute_column_widths(columns)
        for column, width in zip(columns, widths):
            column.width = width
        # 第三步 拼装：统一管线，所有边框字符只来自样式表
        return "\n".join(_assemble(border, columns, widths, len(self._rows)))
