"""texttbl.render：对外入口，只剩 Table 门面。

实现已拆开（输出逐字节不变，tests/ 锁着）：
  - models.py：Cell/Column 数据模型 + 文本换行
  - width.py：显示宽度纯函数（缓存收口在 lru_cache 内）
  - styles.py：四套边框的样式表
  - pipeline.py：网格 → 列宽 → 拼装的统一管线
"""

from texttbl.pipeline import render_table
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
        # 未知样式仍在 render() 时才报错（历史行为）
        border_style = get_style(self._style)
        return render_table(self._headers, self._rows, border_style, self._wrap)
