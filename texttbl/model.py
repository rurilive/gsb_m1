"""Cell/Column 模型：内容、宽度、行高都是数据，字符串拼装不在这里。"""

from texttbl.width import cached_text_width, wrap_text


class Cell(object):
    """一个单元格：原文 + 换行后的行块，宽度/行高构造时算好。"""

    def __init__(self, text, wrap=0):
        self.text = text
        self.lines = wrap_text(text, wrap)
        self.height = len(self.lines)
        self.width = max(cached_text_width(ln) for ln in self.lines)

    def line(self, j):
        """第 j 行文本；超出行高补空串。"""
        if j < self.height:
            return self.lines[j]
        return ""


class Column(object):
    """一列：表头 Cell 打头，列宽 = 全列 Cell 最大宽。"""

    def __init__(self, header):
        self.cells = [header]
        self.width = header.width

    def add(self, cell):
        self.cells.append(cell)
        if cell.width > self.width:
            self.width = cell.width
