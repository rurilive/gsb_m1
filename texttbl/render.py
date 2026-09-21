"""texttbl.render：把二维数据渲染成带边框的文本表格。

监控后台和 CLI 工具在用。2019 年写的，输出被 tests/ 逐字节锁着
（有几个后台直接 diff 表格输出做告警），别动格式。
"""

# 列宽缓存（模块级，历史原因）
_WIDTH_CACHE = {}


def _text_width(s):
    """显示宽度。历史口径：按 len() 算，中文也按 1 个宽。"""
    if s in _WIDTH_CACHE:
        return _WIDTH_CACHE[s]
    w = len(s)
    _WIDTH_CACHE[s] = w
    return w


def _wrap_cell(text, wrap):
    """把单元格文本切成若干行。wrap<=0 不换行。

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
        cols = len(self._headers)
        # 单元格切块（含表头），grid[0] 是表头
        grid = [[_wrap_cell(h, self._wrap) for h in self._headers]]
        for row in self._rows:
            blocks = []
            for i in range(cols):
                if i < len(row):
                    blocks.append(_wrap_cell(row[i], self._wrap))
                else:
                    blocks.append([""])
            grid.append(blocks)
        # 列宽：全表（含表头）逐块扫最大
        widths = []
        for i in range(cols):
            w = 0
            for blocks in grid:
                for ln in blocks[i]:
                    lw = _text_width(ln)
                    if lw > w:
                        w = lw
            widths.append(w)

        out_lines = []
        if self._style == "ascii":
            top = "+" + "+".join(["-" * (w + 2) for w in widths]) + "+"
            mid = "+" + "+".join(["-" * (w + 2) for w in widths]) + "+"
            bot = "+" + "+".join(["-" * (w + 2) for w in widths]) + "+"
            v = "|"
        elif self._style == "light":
            top = "┌" + "┬".join(["─" * (w + 2) for w in widths]) + "┐"
            mid = "├" + "┼".join(["─" * (w + 2) for w in widths]) + "┤"
            bot = "└" + "┴".join(["─" * (w + 2) for w in widths]) + "┘"
            v = "│"
        elif self._style == "heavy":
            top = "┏" + "┳".join(["━" * (w + 2) for w in widths]) + "┓"
            mid = "┣" + "╋".join(["━" * (w + 2) for w in widths]) + "┫"
            bot = "┗" + "┻".join(["━" * (w + 2) for w in widths]) + "┛"
            v = "┃"
        elif self._style == "markdown":
            top = None
            mid = None
            bot = None
            v = "|"
        else:
            raise ValueError("unknown style: %r" % (self._style,))

        if top is not None:
            out_lines.append(top)
        # 表头块（表头也可能换行，逐行渲染）
        hblocks = grid[0]
        hmax = 1
        for b in hblocks:
            if len(b) > hmax:
                hmax = len(b)
        for j in range(hmax):
            parts = []
            for i in range(cols):
                if j < len(hblocks[i]):
                    txt = hblocks[i][j]
                else:
                    txt = ""
                parts.append(" " + txt + " " * (widths[i] - _text_width(txt)) + " ")
            out_lines.append(v + v.join(parts) + v)
        if self._style == "markdown":
            # markdown 的分隔行：横线和列宽一致（历史写法）
            sep = "|"
            for w in widths:
                sep = sep + " " + "-" * w + " |"
            out_lines.append(sep)
        elif len(grid) > 1:
            out_lines.append(mid)
        # 数据行块
        for blocks in grid[1:]:
            rmax = 1
            for b in blocks:
                if len(b) > rmax:
                    rmax = len(b)
            for j in range(rmax):
                parts = []
                for i in range(cols):
                    if j < len(blocks[i]):
                        txt = blocks[i][j]
                    else:
                        txt = ""
                    parts.append(
                        " " + txt + " " * (widths[i] - _text_width(txt)) + " "
                    )
                out_lines.append(v + v.join(parts) + v)
        if bot is not None:
            out_lines.append(bot)
        text = ""
        for ln in out_lines:
            text = text + ln + "\n"
        return text[0:len(text) - 1]
