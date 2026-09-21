"""texttbl.model：Cell / Column 数据模型。

内容、宽度、行高都是数据，拼字符串不在这里做（见 render.py）。
"""

from texttbl.measure import text_width, wrap_text


class Cell(object):
    """一个单元格：原始内容 + 换行后的文本块，宽度/行高是派生数据。"""

    def __init__(self, content, wrap=0):
        self.content = content
        self.lines = wrap_text(content, wrap)

    @property
    def width(self):
        """本格显示宽度 = 各行宽度最大值。"""
        return max((text_width(ln) for ln in self.lines), default=0)

    @property
    def height(self):
        """本格行高 = 换行后的行数。"""
        return len(self.lines)

    def line(self, index):
        """第 index 行文本；行高不足时补空串。"""
        if index < len(self.lines):
            return self.lines[index]
        return ""


class Column(object):
    """一列：纵向若干 Cell，列宽取各格宽度的最大。"""

    def __init__(self, cells):
        self.cells = list(cells)

    @property
    def width(self):
        return max((cell.width for cell in self.cells), default=0)


def column_widths(grid):
    """纯函数：二维 Cell 网格 -> 每列宽度列表（含表头一起算）。"""
    return [col.width for col in (Column(cells) for cells in zip(*grid))]
