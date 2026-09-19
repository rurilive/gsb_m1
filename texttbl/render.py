"""texttbl.render：把二维数据渲染成带边框的文本表格。

监控后台和 CLI 工具在用。2019 年写的，输出被 tests/ 逐字节锁着
（有几个后台直接 diff 表格输出做告警），别动格式。

管线：建 Cell/Column 模型 -> 取列宽 -> 按样式表拼装，见 _build_grid/render。
"""

from texttbl.model import Cell, Column
from texttbl.styles import border_line, get_style
from texttbl.width import cached_text_width


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

    def _build_grid(self):
        """把原始数据建成模型：表头一行 Cell、数据各行 Cell、按列聚合出 Column。"""
        cols = len(self._headers)
        header = [Cell(h, self._wrap) for h in self._headers]
        rows = []
        for row in self._rows:
            rows.append(
                [
                    Cell(row[i], self._wrap) if i < len(row) else Cell("", self._wrap)
                    for i in range(cols)
                ]
            )
        columns = []
        for i in range(cols):
            col = Column(header[i])
            for r in rows:
                col.add(r[i])
            columns.append(col)
        return header, rows, columns

    def render(self):
        style = get_style(self._style)
        header, rows, columns = self._build_grid()
        widths = [c.width for c in columns]
        v = style["v"]

        out_lines = []
        if style["top"] is not None:
            out_lines.append(border_line(style["top"], widths))
        out_lines.extend(_render_block(header, widths, v))
        if style["header_sep"] == "markdown":
            # markdown 的分隔行：横线和列宽一致（历史写法）
            out_lines.append("|" + "".join(" " + "-" * w + " |" for w in widths))
        elif rows:
            out_lines.append(border_line(style["mid"], widths))
        for r in rows:
            out_lines.extend(_render_block(r, widths, v))
        if style["bot"] is not None:
            out_lines.append(border_line(style["bot"], widths))
        return "\n".join(out_lines)


def _render_block(cells, widths, v):
    """把一行 Cell 按行高逐行拼成文本行，左对齐右侧补空格。"""
    height = max(c.height for c in cells)
    lines = []
    for j in range(height):
        parts = []
        for i, cell in enumerate(cells):
            txt = cell.line(j)
            parts.append(" " + txt + " " * (widths[i] - cached_text_width(txt)) + " ")
        lines.append(v + v.join(parts) + v)
    return lines
