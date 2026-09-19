"""表格的数据模型：Cell（单元格）与 Column（列）。

内容、物理行、行高、列宽都是数据；换行、宽度、对齐、边框拼装
各自独立成步，不写在模型里。
"""

from texttbl.width import text_width


def wrap_text(text, wrap):
    """把单元格文本按词贪心切成若干物理行；wrap<=0 不换行。

    连续空白算一个分隔，超长词先清行再硬切。历史口径，逐字节兼容。
    """
    if wrap is None or wrap <= 0:
        return [text]
    tokens = text.split()
    if len(tokens) == 0:
        return [""]
    lines = []
    current = ""
    for word in tokens:
        while text_width(word) > wrap:
            if current != "":
                lines.append(current)
                current = ""
            lines.append(word[0:wrap])
            word = word[wrap:]
        if current == "":
            current = word
        elif text_width(current) + 1 + text_width(word) <= wrap:
            current = current + " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class Cell(object):
    """一个单元格：原始文本 + 换行后的物理行。行高、宽度是派生数据。"""

    __slots__ = ("text", "lines")

    def __init__(self, text, wrap=0):
        self.text = text
        self.lines = wrap_text(text, wrap)

    @classmethod
    def blank(cls):
        return cls("")

    @property
    def height(self):
        return len(self.lines)

    @property
    def width(self):
        w = 0
        for line in self.lines:
            lw = text_width(line)
            if lw > w:
                w = lw
        return w


class Column(object):
    """一列：列序号 + 算好的列宽。当前左对齐，后续可在此挂对齐方向。"""

    __slots__ = ("index", "width")

    def __init__(self, index, width):
        self.index = index
        self.width = width
