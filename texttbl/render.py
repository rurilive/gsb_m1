"""texttbl.render：Table 对外接口 + 统一渲染管线。

管线三步：建 Cell 网格（model.py）-> 算列宽（纯函数）-> 按样式表
拼装（styles.py）。输出被 tests/ 逐字节锁着，格式口径别动。
"""

from texttbl.measure import text_width
from texttbl.model import Cell, column_widths
from texttbl.styles import get_style


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
        style = get_style(self._style)
        grid = self._build_grid()
        widths = column_widths(grid)

        out_lines = []
        if style.frame:
            out_lines.append(_border_line(style, widths, "top"))
        out_lines.extend(_render_row(grid[0], widths, style))
        if style.header_separator == "markdown":
            # markdown 的分隔行：横线和列宽一致（历史写法），空表也画
            out_lines.append(_markdown_separator(style, widths))
        elif len(grid) > 1:
            out_lines.append(_border_line(style, widths, "mid"))
        for row in grid[1:]:
            out_lines.extend(_render_row(row, widths, style))
        if style.frame:
            out_lines.append(_border_line(style, widths, "bot"))
        return "\n".join(out_lines)

    def _build_grid(self):
        """二维 Cell 网格，grid[0] 是表头；缺的格子补空 Cell。"""
        cols = len(self._headers)
        grid = [[Cell(h, self._wrap) for h in self._headers]]
        for row in self._rows:
            grid.append(
                [
                    Cell(row[i] if i < len(row) else "", self._wrap)
                    for i in range(cols)
                ]
            )
        return grid


def _border_line(style, widths, kind):
    """上/中/下边框线：角 + (横线*(列宽+2) + 交叉)*。"""
    left, join, right = (
        (style.top_left, style.top_join, style.top_right)
        if kind == "top"
        else (style.mid_left, style.mid_join, style.mid_right)
        if kind == "mid"
        else (style.bot_left, style.bot_join, style.bot_right)
    )
    return left + join.join([style.horizontal * (w + 2) for w in widths]) + right


def _render_row(cells, widths, style):
    """一行（可能因换行占多行文本）：左对齐，右侧补空格。"""
    height = max((cell.height for cell in cells), default=1)
    lines = []
    for j in range(height):
        parts = []
        for i, cell in enumerate(cells):
            txt = cell.line(j)
            parts.append(" " + txt + " " * (widths[i] - text_width(txt)) + " ")
        lines.append(style.vertical + style.vertical.join(parts) + style.vertical)
    return lines


def _markdown_separator(style, widths):
    return style.vertical + style.vertical.join(
        [" " + style.horizontal * w + " " for w in widths]
    ) + style.vertical
