"""编辑缓冲。

TextBuffer 揣一份文本，replace 改它，scan 整段重扫。
编辑器把每次击键翻成一次 replace，随后拿 scan 的新结果刷界面。
"""

from lexbend.scanner import scan

__all__ = ["BufferError", "TextBuffer"]


class BufferError(Exception):
    """编辑或查询落在文本区间之外。"""


class TextBuffer:
    """文本 + 替换 + 整段重扫。

    replace(start, end, new_text) 把半开区间 [start, end) 换成 new_text，
    返回 (删掉几个字符, 插进几个字符)；越界或不合法抛 BufferError。
    每次编辑都把 scan_count 加一，方便看编辑器到底重扫了多少次。
    """

    def __init__(self, text=""):
        self._text = text
        self._scan_count = 0

    def text(self):
        return self._text

    def __len__(self):
        return len(self._text)

    @property
    def scan_count(self):
        """历史上一共整段重扫了多少次。"""
        return self._scan_count

    def replace(self, start, end, new_text):
        """[start, end) 换成 new_text，返回 (删长, 插长)。"""
        size = len(self._text)
        if start < 0 or end < start or end > size:
            raise BufferError(
                "replace out of range: [%d, %d) in %d" % (start, end, size))
        removed = end - start
        self._text = self._text[:start] + new_text + self._text[end:]
        return removed, len(new_text)

    def insert(self, offset, new_text):
        """在 offset 处插一段，返回 (删长, 插长)。"""
        return self.replace(offset, offset, new_text)

    def delete(self, start, end):
        """删掉 [start, end)，返回 (删长, 插长)。"""
        return self.replace(start, end, "")

    def line_col(self, offset):
        """offset 所在的行列，都从 1 数；offset 等于长度时给文末位置。"""
        size = len(self._text)
        if offset < 0 or offset > size:
            raise BufferError("offset out of range: %d in %d" % (offset, size))
        line = self._text.count("\n", 0, offset) + 1
        line_start = self._text.rfind("\n", 0, offset) + 1
        return line, offset - line_start + 1

    def scan(self):
        """整段重扫，编辑器每敲一键走一次这条路。"""
        self._scan_count += 1
        return scan(self._text)
